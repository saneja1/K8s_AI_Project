"""
Direct test of the new get_pod_memory_comparison tool
"""

import sys
sys.path.insert(0, '/home/K8s_AI_Project/app2.0/MCP/mcp_resources')

from tools_resources import get_pod_memory_comparison

print("Testing get_pod_memory_comparison tool...")
print("=" * 80)

result = get_pod_memory_comparison.invoke({"namespace": "all"})

print(result)
print("=" * 80)
print("\n✅ Tool test completed!")
