# MCP Operations Server Tests

This directory contains test files for validating the MCP Operations Server functionality.

## Related Files

### `k8s_operations_cli.py` (Located in parent directory)

**Purpose:** Standalone command-line interface for all 15 Kubernetes operations tools.

**What it does:**
- Provides CLI access to all operations tools WITHOUT requiring the MCP server
- Directly imports and executes functions from `tools_operations.py`
- Supports all 15 operations with command-line flags and arguments
- Includes help system, dry-run support, and YAML file input

**Use cases:**
- Manual cluster operations from command line
- Scripting and automation
- Testing tools independently of MCP server
- Quick troubleshooting without starting MCP infrastructure

**Example usage:**
```bash
# Scale a deployment
python3 k8s_operations_cli.py scale-deployment nginx default --replicas 3

# Apply YAML configuration
python3 k8s_operations_cli.py apply-yaml deployment.yaml --namespace production

# Delete failed pods
python3 k8s_operations_cli.py delete-pods-by-status Failed --namespace default
```

**Documentation:** See `K8S_OPERATIONS_CLI_README.md` in parent directory

---

## Test Files

### 1. `test_operations_mcp_connection.py`

**Purpose:** Tests if all 15 tools are properly registered and connected to the MCP Operations Server.

**What it tests:**
- Tool registration in the MCP server
- Availability of underlying implementation functions
- Verification that all 15 tools are accessible via the MCP protocol

**Output format:**
```
Connection from MCP Operations Server to 'scale_deployment_tool': ✅ YES/❌ NO
Connection from MCP Operations Server to 'restart_deployment_tool': ✅ YES/❌ NO
...
```

**Run command:**
```bash
cd /home/saneja/K8s_AI_Project/app2.0/MCP/mcp_operations/tests
python3 test_operations_mcp_connection.py
```

**Expected result:** All 15 tools should show ✅ YES (100% connection rate)

---

### 2. `test_operations_mcp_execution.py`

**Purpose:** Tests if all 15 tools can be successfully executed through the MCP Operations Server.

**What it tests:**
- Tool execution via MCP server's `call_tool()` method
- Parameter passing to tools
- Result handling from tool execution
- Uses dry-run/safe parameters to avoid actual cluster changes

**Output format:**
```
1. Testing 'scale_deployment_tool'... ✅ YES/❌ NO
2. Testing 'restart_deployment_tool'... ✅ YES/❌ NO
...
```

**Run command:**
```bash
cd /home/saneja/K8s_AI_Project/app2.0/MCP/mcp_operations/tests
python3 test_operations_mcp_execution.py
```

**Expected result:** All 15 tools should show ✅ YES (100% execution success rate)

---

## All 15 Tools Being Tested

Both test files validate these operations tools:

1. `scale_deployment_tool` - Scale deployments
2. `restart_deployment_tool` - Restart deployments
3. `rollback_deployment_tool` - Rollback deployments
4. `get_deployment_rollout_status_tool` - Get rollout status
5. `delete_deployment_tool` - Delete deployments
6. `delete_pod_tool` - Delete specific pods
7. `delete_pods_by_status_tool` - Bulk delete pods by status
8. `delete_pods_by_label_tool` - Bulk delete pods by label
9. `cordon_node_tool` - Mark nodes unschedulable
10. `uncordon_node_tool` - Mark nodes schedulable
11. `drain_node_tool` - Drain nodes
12. `patch_resource_tool` - Patch resources
13. `create_namespace_tool` - Create namespaces
14. `delete_namespace_tool` - Delete namespaces
15. `apply_yaml_config_tool` - Apply YAML configurations

---

## Test Differences

| Aspect | Connection Test | Execution Test |
|--------|----------------|----------------|
| **Tests** | Tool registration | Tool execution |
| **Method** | Import verification | `call_tool()` invocation |
| **Safety** | Read-only | Uses dry-run parameters |
| **Speed** | Fast (no K8s calls) | Slower (makes actual calls) |
| **Purpose** | Verify MCP wiring | Verify end-to-end functionality |

---

## Prerequisites

- MCP Operations Server module must be importable
- FastMCP library installed (`pip install fastmcp`)
- Virtual environment activated
- Working directory: `/home/saneja/K8s_AI_Project/app2.0/MCP/mcp_operations/tests`

---

## Troubleshooting

### Import Errors
```bash
# Ensure you're in the correct directory
cd /home/saneja/K8s_AI_Project/app2.0/MCP/mcp_operations/tests

# Tests expect parent directory structure:
# tests/
# ../mcp_operations_server.py
# ../tools_operations.py
```

### Path Issues
The tests add parent directory to Python path:
```python
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
```

This allows importing from the parent `mcp_operations` directory.

---

## Success Criteria

✅ **Connection Test:** 15/15 tools registered (100%)  
✅ **Execution Test:** 15/15 tools executable (100%)

Both tests should pass with 100% success rate for a fully functional MCP Operations Server.
