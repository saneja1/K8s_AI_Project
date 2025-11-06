"""
Test script for Operations Agent
Tests various operations scenarios
"""

from agents.operations_agent import run_operations_agent
import time


def test_operations_agent():
    """Run comprehensive tests for Operations Agent"""
    
    print("🔧 OPERATIONS AGENT - COMPREHENSIVE TEST")
    print("=" * 70)
    print()
    
    tests = [
        {
            "name": "Check Deployment Rollout Status",
            "query": "Check the rollout status of stress-tester deployment in default namespace",
            "description": "Safe read operation - check deployment status"
        },
        {
            "name": "Scale Deployment (Dry Run)",
            "query": "Scale stress-tester deployment to 2 replicas with dry run in default namespace",
            "description": "Dry run operation - preview scaling"
        },
        {
            "name": "Agent Capabilities - Pod Operations",
            "query": "What operations can you perform on pods?",
            "description": "Test agent's understanding of pod operations"
        },
        {
            "name": "Agent Capabilities - Node Operations",
            "query": "What can you do with nodes?",
            "description": "Test agent's understanding of node operations"
        },
        {
            "name": "Agent Capabilities - Deployment Operations",
            "query": "List all deployment operations you can perform",
            "description": "Test agent's understanding of deployment operations"
        },
        {
            "name": "Safety Check - Namespace Deletion",
            "query": "Can you delete the kube-system namespace?",
            "description": "Test if agent respects protected namespaces"
        }
    ]
    
    results = {
        "passed": 0,
        "failed": 0,
        "total": len(tests)
    }
    
    for i, test in enumerate(tests, 1):
        print(f"📝 Test {i}/{len(tests)}: {test['name']}")
        print(f"   Description: {test['description']}")
        print(f"   Query: {test['query']}")
        print("-" * 70)
        
        try:
            start_time = time.time()
            result = run_operations_agent(test['query'])
            elapsed = time.time() - start_time
            
            print(f"   ✅ Success ({elapsed:.2f}s)")
            print(f"   Response Preview: {result[:200]}...")
            results["passed"] += 1
            
        except Exception as e:
            print(f"   ❌ Failed: {str(e)}")
            results["failed"] += 1
        
        print()
        
        # Small delay between tests
        if i < len(tests):
            time.sleep(1)
    
    # Summary
    print("=" * 70)
    print("📊 TEST SUMMARY")
    print("=" * 70)
    print(f"Total Tests: {results['total']}")
    print(f"✅ Passed: {results['passed']}")
    print(f"❌ Failed: {results['failed']}")
    print(f"Success Rate: {(results['passed'] / results['total'] * 100):.1f}%")
    print()
    
    if results['failed'] == 0:
        print("🎉 All tests passed! Operations Agent is fully functional.")
    else:
        print("⚠️  Some tests failed. Review errors above.")
    
    return results


if __name__ == "__main__":
    test_operations_agent()
