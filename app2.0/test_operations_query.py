"""
Test Operations Agent with direct queries
"""
from agents.operations_agent import run_operations_agent

def test_query(query: str, test_name: str):
    """Run a single test query"""
    print("\n" + "=" * 80)
    print(f"TEST: {test_name}")
    print("=" * 80)
    print(f"Query: {query}\n")
    
    result = run_operations_agent(query)
    
    print("Agent Response:")
    print("-" * 80)
    print(result)
    print("-" * 80)


if __name__ == "__main__":
    # Test 1: Scale deployment
    test_query(
        "Scale stress-tester deployment to 5 replicas in default namespace",
        "Scale Deployment"
    )
    
    # Test 2: Check rollout status
    test_query(
        "What is the rollout status of stress-tester deployment?",
        "Rollout Status"
    )
    
    # Test 3: Create a new pod using YAML
    test_query(
        """Create a simple nginx pod named 'quick-test' with the image nginx:alpine in default namespace using YAML configuration""",
        "Create Pod via YAML"
    )
    
    print("\n" + "=" * 80)
    print("ALL TESTS COMPLETED")
    print("=" * 80)
