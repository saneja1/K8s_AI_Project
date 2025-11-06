"""
Test the new apply_yaml_config tool in Operations Agent
"""
import asyncio
import sys
import os

from agents.operations_agent import run_operations_agent

def test_apply_yaml_dry_run():
    """Test applying a simple pod YAML configuration (dry-run)"""
    print("\n=== Test 1: Apply Pod YAML (Dry Run) ===")
    
    yaml_content = """
apiVersion: v1
kind: Pod
metadata:
  name: test-nginx-pod
  labels:
    app: nginx
    env: test
spec:
  containers:
  - name: nginx
    image: nginx:latest
    ports:
    - containerPort: 80
"""
    
    query = f"""Apply this YAML configuration to the default namespace (dry-run first):

{yaml_content}

Use dry-run=True to validate before applying."""
    
    result = run_operations_agent(query)
    
    print("\nAgent Response:")
    print("-" * 80)
    print(result)
    print("-" * 80)


def test_apply_configmap():
    """Test applying a ConfigMap YAML configuration"""
    print("\n=== Test 2: Apply ConfigMap YAML ===")
    
    yaml_content = """
apiVersion: v1
kind: ConfigMap
metadata:
  name: test-config
data:
  database.host: "localhost"
  database.port: "5432"
  app.mode: "production"
"""
    
    query = f"""Create this ConfigMap in the default namespace:

{yaml_content}

Apply it (not dry-run) so we can actually create the resource."""
    
    result = run_operations_agent(query)
    
    print("\nAgent Response:")
    print("-" * 80)
    print(result)
    print("-" * 80)


def test_apply_deployment():
    """Test applying a Deployment YAML configuration"""
    print("\n=== Test 3: Apply Deployment YAML ===")
    
    yaml_content = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: test-yaml-deployment
  labels:
    app: test-yaml
spec:
  replicas: 2
  selector:
    matchLabels:
      app: test-yaml
  template:
    metadata:
      labels:
        app: test-yaml
    spec:
      containers:
      - name: nginx
        image: nginx:1.14.2
        ports:
        - containerPort: 80
        resources:
          limits:
            memory: "128Mi"
            cpu: "100m"
"""
    
    query = f"""Create this deployment in the default namespace:

{yaml_content}

Apply it to create a 2-replica nginx deployment with resource limits."""
    
    result = run_operations_agent(query)
    
    print("\nAgent Response:")
    print("-" * 80)
    print(result)
    print("-" * 80)


def test_apply_invalid_yaml():
    """Test safety check for protected namespace"""
    print("\n=== Test 4: Safety Check - Protected Namespace ===")
    
    yaml_content = """
apiVersion: v1
kind: Pod
metadata:
  name: test-pod
spec:
  containers:
  - name: test
    image: nginx
"""
    
    query = f"""Try to apply this YAML to kube-system namespace:

{yaml_content}

This should be blocked by safety check."""
    
    result = run_operations_agent(query)
    
    print("\nAgent Response:")
    print("-" * 80)
    print(result)
    print("-" * 80)


def main():
    """Run all tests"""
    print("=" * 80)
    print("OPERATIONS AGENT - APPLY YAML CONFIG TOOL TESTS")
    print("=" * 80)
    
    try:
        # Test 1: Dry run validation
        test_apply_yaml_dry_run()
        print("\n⏳ Waiting 2 seconds before next test...")
        import time
        time.sleep(2)
        
        # Test 2: Apply ConfigMap
        test_apply_configmap()
        print("\n⏳ Waiting 2 seconds before next test...")
        time.sleep(2)
        
        # Test 3: Apply Deployment
        test_apply_deployment()
        print("\n⏳ Waiting 2 seconds before next test...")
        time.sleep(2)
        
        # Test 4: Safety check
        test_apply_invalid_yaml()
        
        print("\n" + "=" * 80)
        print("ALL TESTS COMPLETED")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ Error during testing: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
