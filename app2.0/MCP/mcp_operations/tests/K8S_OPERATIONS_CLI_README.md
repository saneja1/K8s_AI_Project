# Kubernetes Operations CLI Tool

Standalone command-line interface for all 15 Kubernetes operations tools. This CLI tool provides direct access to K8s operations without requiring the MCP server.

## Location

```bash
/home/saneja/K8s_AI_Project/app2.0/k8s_operations_cli.py
```

## Prerequisites

- Python 3.6+
- Access to Kubernetes cluster via gcloud SSH (configured in tools_operations.py)
- Virtual environment activated: `source .venv/bin/activate`

## Quick Start

```bash
# Activate virtual environment
cd /home/saneja/K8s_AI_Project
source .venv/bin/activate

# Navigate to app2.0 directory
cd app2.0

# Run any command
python3 k8s_operations_cli.py <command> [arguments] [flags]
```

## Available Commands (15 Total)

### Deployment Operations (5 commands)

#### 1. Scale Deployment
```bash
python3 k8s_operations_cli.py scale-deployment <name> <namespace> --replicas <count> [--dry-run]

# Examples:
python3 k8s_operations_cli.py scale-deployment nginx default --replicas 3
python3 k8s_operations_cli.py scale-deployment api-server production --replicas 5 --dry-run
```

#### 2. Restart Deployment
```bash
python3 k8s_operations_cli.py restart-deployment <name> <namespace> [--dry-run]

# Examples:
python3 k8s_operations_cli.py restart-deployment nginx default
python3 k8s_operations_cli.py restart-deployment api-server production --dry-run
```

#### 3. Rollback Deployment
```bash
python3 k8s_operations_cli.py rollback-deployment <name> <namespace> [--revision <num>] [--dry-run]

# Examples:
python3 k8s_operations_cli.py rollback-deployment nginx default
python3 k8s_operations_cli.py rollback-deployment nginx default --revision 3 --dry-run
```

#### 4. Get Deployment Rollout Status
```bash
python3 k8s_operations_cli.py get-deployment-rollout-status <name> <namespace>

# Examples:
python3 k8s_operations_cli.py get-deployment-rollout-status nginx default
```

#### 5. Delete Deployment
```bash
python3 k8s_operations_cli.py delete-deployment <name> [--namespace <ns>] [--force]

# Examples:
python3 k8s_operations_cli.py delete-deployment nginx --namespace default
python3 k8s_operations_cli.py delete-deployment old-api --namespace staging --force
```

---

### Pod Operations (4 commands)

#### 6. Delete Pod
```bash
python3 k8s_operations_cli.py delete-pod <name> <namespace> [--grace-period <seconds>] [--force]

# Examples:
python3 k8s_operations_cli.py delete-pod nginx-pod-123 default
python3 k8s_operations_cli.py delete-pod stuck-pod default --force
python3 k8s_operations_cli.py delete-pod api-pod production --grace-period 10
```

#### 7. Delete Pods by Status
```bash
python3 k8s_operations_cli.py delete-pods-by-status <status> [--namespace <ns>] [--force]

# Valid statuses: Failed, Pending, Unknown, Error, CrashLoopBackOff

# Examples:
python3 k8s_operations_cli.py delete-pods-by-status Failed --namespace default
python3 k8s_operations_cli.py delete-pods-by-status CrashLoopBackOff --namespace all --force
```

#### 8. Delete Pods by Label
```bash
python3 k8s_operations_cli.py delete-pods-by-label <label_selector> [--namespace <ns>] [--force]

# Examples:
python3 k8s_operations_cli.py delete-pods-by-label "app=nginx" --namespace default
python3 k8s_operations_cli.py delete-pods-by-label "env=dev,tier=frontend" --namespace all
```

#### 9. Apply YAML Configuration
```bash
python3 k8s_operations_cli.py apply-yaml <yaml_file> [--namespace <ns>] [--dry-run]

# Examples:
python3 k8s_operations_cli.py apply-yaml deployment.yaml --namespace production
python3 k8s_operations_cli.py apply-yaml service.yaml --namespace default --dry-run
python3 k8s_operations_cli.py apply-yaml configmap.yaml --namespace dev
```

**Supports creating/updating:**
- Pods
- Deployments
- Services
- ConfigMaps
- Secrets
- Ingress
- Jobs
- CronJobs
- DaemonSets
- StatefulSets
- And more...

---

### Node Operations (3 commands)

#### 10. Cordon Node
```bash
python3 k8s_operations_cli.py cordon-node <node_name>

# Examples:
python3 k8s_operations_cli.py cordon-node worker-1
```

#### 11. Uncordon Node
```bash
python3 k8s_operations_cli.py uncordon-node <node_name>

# Examples:
python3 k8s_operations_cli.py uncordon-node worker-1
```

#### 12. Drain Node
```bash
python3 k8s_operations_cli.py drain-node <node_name> [--force] [--ignore-daemonsets] [--delete-emptydir-data]

# Examples:
python3 k8s_operations_cli.py drain-node worker-1
python3 k8s_operations_cli.py drain-node worker-2 --force --ignore-daemonsets
python3 k8s_operations_cli.py drain-node worker-3 --delete-emptydir-data
```

---

### Advanced Operations (3 commands)

#### 13. Patch Resource
```bash
python3 k8s_operations_cli.py patch-resource <resource_type> <name> <namespace> --patch-json '<json>' [--dry-run]

# Examples:
python3 k8s_operations_cli.py patch-resource deployment nginx default --patch-json '{"spec":{"replicas":5}}'
python3 k8s_operations_cli.py patch-resource service api-svc production --patch-json '{"spec":{"type":"LoadBalancer"}}' --dry-run
```

#### 14. Create Namespace
```bash
python3 k8s_operations_cli.py create-namespace <name> [--dry-run]

# Examples:
python3 k8s_operations_cli.py create-namespace development
python3 k8s_operations_cli.py create-namespace staging --dry-run
```

#### 15. Delete Namespace
```bash
python3 k8s_operations_cli.py delete-namespace <name> [--force]

# Examples:
python3 k8s_operations_cli.py delete-namespace old-env
python3 k8s_operations_cli.py delete-namespace test-env --force
```

---

## Common Flags

- `--dry-run` - Test the operation without applying changes (validation only)
- `--force` - Force immediate deletion (skip grace period)
- `--namespace` - Target namespace (varies by command)
- `--grace-period` - Grace period in seconds for pod deletion (default: 30)
- `--help` - Show help for any command

## Usage Patterns

### Get Help
```bash
# General help
python3 k8s_operations_cli.py --help

# Command-specific help
python3 k8s_operations_cli.py scale-deployment --help
python3 k8s_operations_cli.py apply-yaml --help
```

### Test Before Applying (Dry Run)
```bash
# Always test destructive operations first
python3 k8s_operations_cli.py delete-deployment nginx --namespace default --dry-run
python3 k8s_operations_cli.py scale-deployment api production --replicas 10 --dry-run
```

### Apply YAML from File
```bash
# Create a YAML file first
cat > test-deployment.yaml <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: test-nginx
spec:
  replicas: 2
  selector:
    matchLabels:
      app: nginx
  template:
    metadata:
      labels:
        app: nginx
    spec:
      containers:
      - name: nginx
        image: nginx:latest
        ports:
        - containerPort: 80
EOF

# Apply it
python3 k8s_operations_cli.py apply-yaml test-deployment.yaml --namespace default
```

## Architecture

```
CLI Tool (k8s_operations_cli.py)
    ↓
Imports tools_operations.py
    ↓
Executes kubectl commands via gcloud SSH
    ↓
Returns formatted results
```

## Key Features

✅ **Standalone** - Works independently of MCP server
✅ **Complete** - All 15 operations from MCP Operations Server
✅ **Safe** - Built-in dry-run and safety checks
✅ **Flexible** - File input for YAML, various flags
✅ **User-friendly** - Clear help messages and examples
✅ **No modifications** - Original MCP tools untouched

## Differences from MCP Server

| Feature | MCP Server | CLI Tool |
|---------|-----------|----------|
| Transport | HTTP/MCP Protocol | Direct Python execution |
| Client | Claude Desktop/MCP clients | Command line |
| Port | 8003 | N/A |
| Use Case | AI agent integration | Manual operations |
| Setup | Server must be running | Just run the script |

## Safety Features

- **Dry-run mode** for testing operations
- **Safety checks** for protected namespaces (kube-system, etc.)
- **Bulk operation limits** (max 10 pods for bulk deletes)
- **Grace periods** for pod deletion (default 30 seconds)
- **Clear error messages** with actionable feedback

## Troubleshooting

### Command Not Found
```bash
# Make sure you're in the right directory
cd /home/saneja/K8s_AI_Project/app2.0

# Check file exists
ls -la k8s_operations_cli.py
```

### Import Errors
```bash
# Ensure MCP/mcp_operations/tools_operations.py exists
ls -la MCP/mcp_operations/tools_operations.py

# Activate virtual environment
source ../venv/bin/activate
```

### Connection Errors
- Verify gcloud configuration is set up
- Check SSH access to k8s-master-001
- Ensure KUBECONFIG path is correct in tools_operations.py

## Examples Workflow

```bash
# 1. List all available commands
python3 k8s_operations_cli.py --help

# 2. Check deployment status
python3 k8s_operations_cli.py get-deployment-rollout-status nginx default

# 3. Scale deployment (dry-run first)
python3 k8s_operations_cli.py scale-deployment nginx default --replicas 5 --dry-run
python3 k8s_operations_cli.py scale-deployment nginx default --replicas 5

# 4. Create namespace
python3 k8s_operations_cli.py create-namespace testing

# 5. Apply configuration
python3 k8s_operations_cli.py apply-yaml my-app.yaml --namespace testing --dry-run
python3 k8s_operations_cli.py apply-yaml my-app.yaml --namespace testing

# 6. Clean up failed pods
python3 k8s_operations_cli.py delete-pods-by-status Failed --namespace testing

# 7. Delete namespace when done
python3 k8s_operations_cli.py delete-namespace testing
```

## Summary

This CLI tool provides a **complete, standalone interface** to all 15 Kubernetes operations tools without requiring the MCP server to be running. It's ideal for:

- Manual cluster operations
- Scripting and automation
- Testing operations before integrating with AI agents
- Quick troubleshooting and maintenance
- Learning the available operations

All operations are identical to the MCP server tools - they use the same underlying `tools_operations.py` functions.
