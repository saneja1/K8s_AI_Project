# Kubernetes Multi-Agent Tools Architecture
## Hybrid Approach with Generic + Specialized Tools

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                         SUPERVISOR AGENT (Router & Orchestrator)                     │
│                    Routes questions to appropriate specialist agents                 │
└──────────────────────────────────┬──────────────────────────────────────────────────┘
                                   │
                                   │ Routes to appropriate agent
                                   │
        ┌──────────────────────────┼──────────────────────────┐
        │                          │                          │
        ▼                          ▼                          ▼
┌───────────────────┐    ┌───────────────────┐    ┌───────────────────┐
│  HEALTH AGENT     │    │  SECURITY AGENT   │    │  RESOURCES AGENT  │
│  (Node/Cluster)   │    │  (RBAC/Policies)  │    │  (CPU/Memory)     │
└─────────┬─────────┘    └─────────┬─────────┘    └─────────┬─────────┘
          │                        │                        │
          ▼                        ▼                        ▼
    
    ┌─────────────────────────────────────────────────────────┐
    │              HEALTH TOOLS (3 tools)                     │
    ├─────────────────────────────────────────────────────────┤
    │ 1. check_node_health                                    │
    │    └─ Check specific node (conditions, taints)          │
    │                                                          │
    │ 2. check_cluster_health                                 │
    │    └─ Overview of all nodes (status, roles, IPs)        │
    │                                                          │
    │ 3. execute_kubectl (GENERIC - health queries)           │
    │    └─ Any kubectl command for health checks             │
    │       Examples:                                          │
    │       • "get nodes -o json"                             │
    │       • "get componentstatuses"                         │
    │       • "get --raw /healthz"                            │
    └─────────────────────────────────────────────────────────┘

    ┌─────────────────────────────────────────────────────────┐
    │            SECURITY TOOLS (4 tools)                     │
    ├─────────────────────────────────────────────────────────┤
    │ 1. check_rbac_permissions (NEW)                         │
    │    └─ Check user/service account permissions            │
    │                                                          │
    │ 2. list_secrets_and_configmaps (NEW)                    │
    │    └─ List secrets/configmaps (masked values)           │
    │                                                          │
    │ 3. check_network_policies (NEW)                         │
    │    └─ List network policies and ingress rules           │
    │                                                          │
    │ 4. execute_kubectl (GENERIC - security queries)         │
    │    └─ Any kubectl command for security                  │
    │       Examples:                                          │
    │       • "get rolebindings -A"                           │
    │       • "get podsecuritypolicies"                       │
    │       • "auth can-i --list"                             │
    └─────────────────────────────────────────────────────────┘

    ┌─────────────────────────────────────────────────────────┐
    │           RESOURCES TOOLS (4 tools)                     │
    ├─────────────────────────────────────────────────────────┤
    │ 1. get_resource_usage (NEW)                             │
    │    └─ kubectl top nodes/pods with usage analysis        │
    │                                                          │
    │ 2. get_resource_quotas (NEW)                            │
    │    └─ Check namespace quotas and limits                 │
    │                                                          │
    │ 3. analyze_resource_requests (NEW)                      │
    │    └─ Compare requests vs actual usage                  │
    │                                                          │
    │ 4. execute_kubectl (GENERIC - resource queries)         │
    │    └─ Any kubectl command for resources                 │
    │       Examples:                                          │
    │       • "top pods --containers"                         │
    │       • "describe quota"                                │
    │       • "get limitranges -A"                            │
    └─────────────────────────────────────────────────────────┘


        ┌──────────────────────────┼──────────────────────────┐
        │                          │                          │
        ▼                          ▼                          ▼
┌───────────────────┐    ┌───────────────────┐    ┌───────────────────┐
│  MONITOR AGENT    │    │ DESCRIBE-GET      │    │  OPERATIONS       │
│  (Logs/Events)    │    │ AGENT (Resources) │    │  AGENT (Actions)  │
└─────────┬─────────┘    └─────────┬─────────┘    └─────────┬─────────┘
          │                        │                        │
          ▼                        ▼                        ▼

    ┌─────────────────────────────────────────────────────────┐
    │            MONITOR TOOLS (4 tools)                      │
    ├─────────────────────────────────────────────────────────┤
    │ 1. get_pod_logs                                         │
    │    └─ Get logs (supports partial name matching)         │
    │                                                          │
    │ 2. get_cluster_events (NEW)                             │
    │    └─ Recent events sorted by timestamp                 │
    │                                                          │
    │ 3. troubleshoot_pod (NEW - WORKFLOW)                    │
    │    └─ Complete pod analysis:                            │
    │       ├─ Status & conditions                            │
    │       ├─ Recent logs (last 100 lines)                   │
    │       ├─ Events related to pod                          │
    │       └─ Describe output with key sections              │
    │                                                          │
    │ 4. execute_kubectl (GENERIC - monitoring queries)       │
    │    └─ Any kubectl command for monitoring                │
    │       Examples:                                          │
    │       • "logs pod-name --previous"                      │
    │       • "get events --field-selector type=Warning"      │
    │       • "logs -l app=nginx --tail=50"                   │
    └─────────────────────────────────────────────────────────┘

    ┌─────────────────────────────────────────────────────────┐
    │         DESCRIBE-GET TOOLS (3 tools)                    │
    ├─────────────────────────────────────────────────────────┤
    │ 1. get_cluster_resources                                │
    │    └─ List any K8s resource (JSON output)               │
    │                                                          │
    │ 2. describe_resource                                    │
    │    └─ Detailed info about specific resource             │
    │                                                          │
    │ 3. execute_kubectl (GENERIC - describe/get queries)     │
    │    └─ Any kubectl command for listing/describing        │
    │       Examples:                                          │
    │       • "get all -A"                                    │
    │       • "get crd"                                       │
    │       • "api-resources"                                 │
    └─────────────────────────────────────────────────────────┘

    ┌─────────────────────────────────────────────────────────┐
    │         OPERATIONS TOOLS (6 tools) **NEW AGENT**        │
    ├─────────────────────────────────────────────────────────┤
    │ 1. delete_pod (NEW - with confirmation)                 │
    │    └─ Delete pod with safety confirmation               │
    │       ├─ Show pod details first                         │
    │       ├─ Require explicit confirmation                  │
    │       └─ Validate pod exists before deletion            │
    │                                                          │
    │ 2. scale_deployment (NEW - with confirmation)           │
    │    └─ Scale deployment replicas                         │
    │       ├─ Show current replica count                     │
    │       ├─ Require explicit confirmation                  │
    │       ├─ Validate new replica count (1-100)             │
    │       └─ Show scaling progress                          │
    │                                                          │
    │ 3. restart_deployment (NEW - with confirmation)         │
    │    └─ Restart deployment (rollout restart)              │
    │       ├─ Show deployment details                        │
    │       ├─ Require explicit confirmation                  │
    │       └─ Monitor restart progress                       │
    │                                                          │
    │ 4. delete_failed_pods (NEW - with confirmation)         │
    │    └─ Delete all failed/completed pods in namespace     │
    │       ├─ List failed pods first                         │
    │       ├─ Show count (max 50 at once)                    │
    │       ├─ Require explicit confirmation                  │
    │       └─ Delete with grace period                       │
    │                                                          │
    │ 5. cordon_drain_node (NEW - with confirmation)          │
    │    └─ Cordon/drain node for maintenance                 │
    │       ├─ Show pods on node                              │
    │       ├─ Require explicit confirmation                  │
    │       └─ Monitor eviction progress                      │
    │                                                          │
    │ 6. execute_kubectl (GENERIC - operation commands)       │
    │    └─ Any kubectl command for operations                │
    │       Examples:                                          │
    │       • "apply -f manifest.yaml"                        │
    │       • "rollout status deployment/nginx"               │
    │       • "patch deployment nginx -p '{...}'"             │
    │                                                          │
    │ ⚠️  SAFETY FEATURES FOR ALL OPERATIONS:                 │
    │    ├─ Dry-run option available                          │
    │    ├─ Confirmation required for destructive actions     │
    │    ├─ Validation before execution                       │
    │    └─ Detailed logging of all operations                │
    └─────────────────────────────────────────────────────────┘


════════════════════════════════════════════════════════════════════════════════════

                            TOOL DISTRIBUTION SUMMARY

════════════════════════════════════════════════════════════════════════════════════

┌──────────────────────────┬───────────────────┬────────────────────────────────────┐
│ AGENT                    │ SPECIALIZED TOOLS │ GENERIC TOOL ACCESS                │
├──────────────────────────┼───────────────────┼────────────────────────────────────┤
│ Health Agent             │        2          │ execute_kubectl (health scope)     │
│ Security Agent           │        3          │ execute_kubectl (security scope)   │
│ Resources Agent          │        3          │ execute_kubectl (resources scope)  │
│ Monitor Agent            │        3          │ execute_kubectl (monitoring scope) │
│ Describe-Get Agent       │        2          │ execute_kubectl (describe scope)   │
│ Operations Agent (NEW)   │        5          │ execute_kubectl (operations scope) │
├──────────────────────────┼───────────────────┼────────────────────────────────────┤
│ TOTAL                    │       18          │ 1 (shared across all agents)       │
└──────────────────────────┴───────────────────┴────────────────────────────────────┘

TOTAL TOOLS IN SYSTEM: 19 tools (18 specialized + 1 generic)
Coverage: ~90% of all Kubernetes operations


════════════════════════════════════════════════════════════════════════════════════

                           GENERIC TOOL MECHANISM

════════════════════════════════════════════════════════════════════════════════════

                              execute_kubectl(command, namespace)
                                           │
                                           │ Shared by all agents
                                           │
                    ┌──────────────────────┼──────────────────────┐
                    │                      │                      │
                    ▼                      ▼                      ▼
              ┌───────────┐          ┌───────────┐        ┌───────────┐
              │  Health   │          │ Security  │        │  Monitor  │
              │  queries  │          │  queries  │        │  queries  │
              └───────────┘          └───────────┘        └───────────┘
                    │                      │                      │
                    └──────────────────────┼──────────────────────┘
                                           │
                                           ▼
                                 ┌──────────────────┐
                                 │ SSH to K8s Master│
                                 │ kubectl [command]│
                                 └──────────────────┘


════════════════════════════════════════════════════════════════════════════════════

                     CONFIRMATION FLOW FOR DESTRUCTIVE OPERATIONS

════════════════════════════════════════════════════════════════════════════════════

User: "Delete pod nginx-abc123"
   │
   ▼
Supervisor → Routes to Operations Agent
   │
   ▼
Operations Agent: Calls delete_pod("nginx-abc123", namespace="default")
   │
   ▼
┌────────────────────────────────────────────────────────────────────────────────┐
│ delete_pod TOOL WORKFLOW:                                                      │
│                                                                                 │
│ Step 1: VALIDATE                                                               │
│    ├─ Check if pod exists                                                      │
│    ├─ Get pod status, age, restart count                                       │
│    └─ Return error if pod not found                                            │
│                                                                                 │
│ Step 2: SHOW DETAILS                                                           │
│    ├─ Pod Name: nginx-abc123                                                   │
│    ├─ Namespace: default                                                       │
│    ├─ Status: Running                                                          │
│    ├─ Age: 2d5h                                                                │
│    └─ Restart Count: 3                                                         │
│                                                                                 │
│ Step 3: REQUEST CONFIRMATION                                                   │
│    └─ "⚠️  Are you sure you want to delete pod 'nginx-abc123' in namespace    │
│         'default'? This action cannot be undone.                               │
│         Reply 'yes delete' to confirm or 'cancel' to abort."                   │
│                                                                                 │
│ Step 4: WAIT FOR USER RESPONSE                                                 │
│    ├─ If "yes delete" → Proceed to Step 5                                      │
│    ├─ If "cancel" → Abort and return                                           │
│    └─ If other → Ask for clarification                                         │
│                                                                                 │
│ Step 5: EXECUTE DELETION                                                       │
│    ├─ Run: kubectl delete pod nginx-abc123 -n default --grace-period=30       │
│    ├─ Log command execution                                                    │
│    └─ Monitor deletion status                                                  │
│                                                                                 │
│ Step 6: REPORT RESULT                                                          │
│    └─ "✅ Pod 'nginx-abc123' deleted successfully from namespace 'default'"   │
│        or                                                                       │
│        "❌ Failed to delete pod: [error details]"                              │
└────────────────────────────────────────────────────────────────────────────────┘


════════════════════════════════════════════════════════════════════════════════════

                         EXAMPLE USER INTERACTIONS

════════════════════════════════════════════════════════════════════════════════════

┌────────────────────────────────────────────────────────────────────────────────┐
│ SCENARIO 1: Health Check                                                       │
├────────────────────────────────────────────────────────────────────────────────┤
│ User: "Are all nodes healthy?"                                                 │
│   ↓                                                                             │
│ Supervisor → Health Agent                                                      │
│   ↓                                                                             │
│ Health Agent uses: check_cluster_health()                                      │
│   ↓                                                                             │
│ Response: "✅ All 3 nodes are Ready. No taints found."                         │
└────────────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────────────┐
│ SCENARIO 2: Troubleshooting                                                    │
├────────────────────────────────────────────────────────────────────────────────┤
│ User: "Why is nginx pod crashing?"                                             │
│   ↓                                                                             │
│ Supervisor → Monitor Agent                                                     │
│   ↓                                                                             │
│ Monitor Agent uses: troubleshoot_pod("nginx")                                  │
│   ↓ (internally calls multiple kubectl commands)                               │
│   ├─ Get pod status                                                            │
│   ├─ Get recent logs                                                           │
│   ├─ Get events                                                                │
│   └─ Describe pod                                                              │
│   ↓                                                                             │
│ Response: "Pod is CrashLoopBackOff. Last error: 'Config file not found'.       │
│            Events show: Failed to mount configmap 'nginx-config'."             │
└────────────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────────────┐
│ SCENARIO 3: Resource Check                                                     │
├────────────────────────────────────────────────────────────────────────────────┤
│ User: "Which pods are using most CPU?"                                         │
│   ↓                                                                             │
│ Supervisor → Resources Agent                                                   │
│   ↓                                                                             │
│ Resources Agent uses: get_resource_usage("pods")                               │
│   ↓                                                                             │
│ Response: "Top 3 CPU consumers:                                                │
│            1. database-0: 850m (85% of limit)                                  │
│            2. api-server: 420m (42% of limit)                                  │
│            3. worker-1: 280m (28% of limit)"                                   │
└────────────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────────────┐
│ SCENARIO 4: Pod Deletion (WITH CONFIRMATION)                                   │
├────────────────────────────────────────────────────────────────────────────────┤
│ User: "Delete the failed pod in default namespace"                             │
│   ↓                                                                             │
│ Supervisor → Operations Agent                                                  │
│   ↓                                                                             │
│ Operations Agent uses: delete_failed_pods("default")                           │
│   ↓                                                                             │
│ Agent: "Found 2 failed pods in namespace 'default':                            │
│         • nginx-abc123 (Error: CrashLoopBackOff)                               │
│         • worker-xyz789 (Failed: ImagePullBackOff)                             │
│         ⚠️  Delete these 2 pods? Reply 'yes delete' to confirm."              │
│   ↓                                                                             │
│ User: "yes delete"                                                              │
│   ↓                                                                             │
│ Agent executes deletion                                                         │
│   ↓                                                                             │
│ Response: "✅ Deleted 2 failed pods:                                           │
│            • nginx-abc123 - deleted                                             │
│            • worker-xyz789 - deleted"                                           │
└────────────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────────────┐
│ SCENARIO 5: Scale Deployment (WITH CONFIRMATION)                               │
├────────────────────────────────────────────────────────────────────────────────┤
│ User: "Scale nginx deployment to 5 replicas"                                   │
│   ↓                                                                             │
│ Supervisor → Operations Agent                                                  │
│   ↓                                                                             │
│ Operations Agent uses: scale_deployment("nginx", replicas=5, namespace="...")  │
│   ↓                                                                             │
│ Agent: "Current: nginx deployment has 3 replicas                               │
│         Target: Scale to 5 replicas (+2)                                       │
│         ⚠️  Proceed with scaling? Reply 'yes scale' to confirm."              │
│   ↓                                                                             │
│ User: "yes scale"                                                               │
│   ↓                                                                             │
│ Agent executes: kubectl scale deployment nginx --replicas=5                    │
│   ↓                                                                             │
│ Response: "✅ Deployment 'nginx' scaled to 5 replicas.                         │
│            Status: 5/5 ready"                                                   │
└────────────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────────────┐
│ SCENARIO 6: Generic kubectl Command                                            │
├────────────────────────────────────────────────────────────────────────────────┤
│ User: "Show me all custom resource definitions"                                │
│   ↓                                                                             │
│ Supervisor → Describe-Get Agent                                                │
│   ↓                                                                             │
│ Agent uses: execute_kubectl("get crd")                                         │
│   ↓ (LLM constructed the right command)                                        │
│ Response: "Found 8 custom resources:                                           │
│            • certificates.cert-manager.io                                       │
│            • issuers.cert-manager.io                                            │
│            • [...more CRDs...]"                                                 │
└────────────────────────────────────────────────────────────────────────────────┘


════════════════════════════════════════════════════════════════════════════════════

                              IMPLEMENTATION SUMMARY

════════════════════════════════════════════════════════════════════════════════════

AGENTS:          6 (Health, Security, Resources, Monitor, Describe-Get, Operations)
TOOLS:          19 (18 specialized + 1 generic shared)
COVERAGE:       ~90% of Kubernetes operations
SAFETY:         Confirmation required for all destructive operations
FLEXIBILITY:    Generic tool handles edge cases and new kubectl features

KEY BENEFITS:
✅ Minimal tool count (19 vs 100+)
✅ Maximum coverage (90% of K8s operations)
✅ Safe operations (confirmation + validation)
✅ Future-proof (generic tool adapts to new kubectl features)
✅ Smart routing (supervisor sends questions to right expert)
```
