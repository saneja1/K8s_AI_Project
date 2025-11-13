# Kubernetes AI Agent - Multi-Agent System with MCP Architecture

A CLI tool that uses AI agents with Model Context Protocol (MCP) servers to query and manage Kubernetes clusters through natural language.

## 🏗️ Architecture Overview (MCP-Based)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         USER (CLI Interface)                                 │
│                   python cli.py -q "your question"                           │
└────────────────────────────────┬─────────────────────────────────────────────┘
                                 │
                                 │ Natural Language Query
                                 ▼
                  ┌──────────────────────────────────────┐
                  │   Kubernetes Supervisor Agent        │
                  │        (k8s_agent.py)                │
                  │                                      │
                  │  • Query classification (LLM)        │
                  │  • Sub-question extraction           │
                  │  • Parallel agent execution (5 max)  │
                  │  • Response synthesis                │
                  │  • Claude 3 Haiku (fast)             │
                  └──────────────┬───────────────────────┘
                                 │
             ┌───────────────────┼─────────────────────┐
             │                   │                     │
    ┌────────▼────────┐ ┌───────▼────────┐ ┌─────────▼────────┐
    │  Health Agent   │ │ Describe Agent │ │ Resources Agent  │
    │ health_agent.py │ │ describe_      │ │ resources_       │
    │                 │ │ agent.py       │ │ agent.py         │
    │ Node health,    │ │                │ │                  │
    │ cluster events, │ │ List/count     │ │ CPU/memory       │
    │ control plane   │ │ resources,     │ │ capacity,        │
    │                 │ │ pod status     │ │ utilization      │
    └────────┬────────┘ └───────┬────────┘ └─────────┬────────┘
             │                  │                     │
    ┌────────▼────────┐ ┌───────▼────────┐           │
    │ Monitor Agent   │ │ Operations     │           │
    │ monitor_        │ │ Agent          │           │
    │ agent.py        │ │ operations_    │           │
    │                 │ │ agent.py       │           │
    │ Prometheus      │ │                │           │
    │ metrics,        │ │ Scale, delete, │           │
    │ real-time data, │ │ restart, node  │           │
    │ trends          │ │ maintenance    │           │
    └────────┬────────┘ └───────┬────────┘           │
             │                  │                     │
             │ MCP Client       │ MCP Client          │ MCP Client
             │ (HTTP)           │ (HTTP)              │ (HTTP)
             ▼                  ▼                     ▼
    ┌─────────────────┐ ┌──────────────────┐ ┌─────────────────┐
    │  MCP Health     │ │  MCP Describe    │ │ MCP Resources   │
    │  Server         │ │  Server          │ │ Server          │
    │  Port: 8000     │ │  Port: 8002      │ │ Port: NOT USED  │
    │                 │ │                  │ │ (Direct kubectl)│
    │ Tools (3):      │ │ Tools (5):       │ │ Tools (6):      │
    │ • nodes list    │ │ • list resources │ │ • node capacity │
    │ • node describe │ │ • describe K8s   │ │ • pod limits    │
    │ • cluster events│ │ • count resources│ │ • namespace agg │
    │                 │ │ • get all        │ │ • node usage    │
    │                 │ │ • get YAML       │ │ • pod usage     │
    │                 │ │                  │ │ • CPU/mem compare│
    └────────┬────────┘ └──────┬───────────┘ └───────┬─────────┘
             │                 │                      │
    ┌────────▼────────┐ ┌──────▼───────────┐         │
    │  MCP Monitor    │ │  MCP Operations  │         │
    │  Server         │ │  Server          │         │
    │  Port: 8004     │ │  Port: 8003      │         │
    │                 │ │                  │         │
    │ Tools (6):      │ │ Tools (15):      │         │
    │ • query instant │ │ • scale deploy   │         │
    │ • query range   │ │ • restart deploy │         │
    │ • get node      │ │ • rollback       │         │
    │   metrics       │ │ • delete pod     │         │
    │ • get pod       │ │ • delete deploy  │         │
    │   metrics       │ │ • cordon node    │         │
    │ • get top pods  │ │ • drain node     │         │
    │ • check targets │ │ • patch resource │         │
    │                 │ │ • apply YAML     │         │
    └────────┬────────┘ └──────┬───────────┘         │
             │                 │                      │
             │ Prometheus API  │ kubectl via SSH      │
             │                 │                      │
             ▼                 └──────────────────────┼────────┐
    ┌───────────────────┐                            │        │
    │  Prometheus       │                            ▼        ▼
    │  34.59.188.124    │             ┌─────────────────────────────┐
    │  :9090            │             │  Google Cloud VM            │
    │                   │             │  k8s-master-001             │
    │  Metrics backend  │             │                             │
    │  (node_exporter)  │             │  Kubernetes Cluster         │
    └───────────────────┘             │  • k8s-master-001 (Master)  │
                                      │  • k8s-worker-01 (Worker)   │
                                      └─────────────────────────────┘
```

## 🚀 What is MCP (Model Context Protocol)?

**MCP** is a protocol that allows AI agents to connect to external tool servers. Think of it as a standardized way for AI agents to access tools - like a "USB port" for AI agents.

### Why MCP Architecture?

**Traditional Approach** (what we moved away from):
```
Agent → Direct tool imports → Tools in same process
```
- ❌ All tools loaded in memory even if unused (bloated agent processes)
- ❌ Hard to share tools across multiple agents (code duplication)
- ❌ Difficult to scale (everything in one process)
- ❌ Tool changes require agent restart

**MCP Approach** (current architecture):
```
Agent → MCP Client → HTTP → MCP Server → Tools
```
- ✅ **Process isolation**: Tools run in separate processes (crash doesn't kill agent)
- ✅ **Tool sharing**: Multiple agents connect to same MCP server (e.g., Operations Server used by Operations Agent)
- ✅ **Lazy loading**: Tools loaded only when MCP server is hit
- ✅ **Server-level caching**: 60s TTL for kubectl commands benefits all connected agents
- ✅ **Hot reload**: Restart MCP server without affecting agents
- ✅ **Easier maintenance**: Add new agent by connecting to existing servers (no tool reimplementation)

### Real-World Analogy

Think of it like microservices for AI agents:
- **Without MCP**: Monolithic agent with all tools bundled (like a monolithic web app)
- **With MCP**: Agent connects to tool servers (like microservices architecture)

### Why We Use It

Our system has **5 agents** and **4 MCP servers**:
1. **Health Agent** → MCP Health Server (port 8000)
2. **Describe Agent** → MCP Describe Server (port 8002)  
3. **Operations Agent** → MCP Operations Server (port 8003)
4. **Monitor Agent** → MCP Monitor Server (port 8004)
5. **Resources Agent** → Direct kubectl (no MCP server - simpler for direct execution)
6. **Supervisor Agent** → Routes to other 5 agents (orchestration only)

Benefits we get:
- Monitor Agent can query Prometheus independently (MCP Monitor Server)
- Operations Agent can execute write operations safely (isolated process)
- If Health Server crashes, other agents continue working
- Each server has 60s cache → faster repeated queries
- Can restart Prometheus/kubectl tools without restarting agents

## 📋 Agent Details

### 1. **Health Agent** 🏥
**Responsibility**: Node-level and cluster-level health monitoring

**MCP Server**: `http://localhost:8000/mcp`
- Port: 8000
- File: `MCP/mcp_health/mcp_health_server.py`
- Framework: FastMCP

**Tools (3)**:
1. **get_cluster_nodes**: List all nodes with Ready/NotReady status
2. **describe_node**: Detailed node conditions (MemoryPressure, DiskPressure, PIDPressure)
3. **get_cluster_events**: Recent cluster warnings and errors

**What It Does**:
- Checks if nodes are Ready/NotReady
- Identifies node-level issues (memory pressure, disk pressure, PID pressure)
- Shows cluster-wide warnings and errors
- **Does NOT handle pod health** - that's Describe Agent's job

**Example Queries**:
- "Are all nodes healthy?"
- "Is there memory pressure on any node?"
- "Show cluster warnings"
- "Check control plane health"

**Agent File**: `agents/health_agent.py`

---

### 2. **Describe Agent** 📝
**Responsibility**: Resource discovery, listing, and pod status

**MCP Server**: `http://localhost:8002/mcp`
- Port: 8002
- File: `MCP/mcp_describe/mcp_describe_server.py`
- Framework: FastMCP

**Tools (5)**:
1. **list_k8s_resources**: List ANY K8s resource (pods, services, deployments, etc.)
2. **describe_k8s_resource**: Get detailed info about specific resource
3. **count_k8s_resources**: Count resources with filtering (status, namespace, node)
4. **get_all_resources_in_namespace**: Quick overview of namespace contents
5. **get_resource_yaml**: Get YAML definition

**Special Capability**: Pod health/status checking
- Checks pod STATUS field (Running/Failed/Pending/CrashLoopBackOff)
- Identifies unhealthy or failing pods
- **Note**: Pod health belongs to Describe, not Health Agent!

**What It Does**:
- List and count Kubernetes resources (pods, deployments, services, etc.)
- Check pod status (Running, Failed, CrashLoopBackOff)
- Get YAML definitions of resources
- Generic tool works with ANY resource type (no hardcoding)

**Example Queries**:
- "How many pods in the cluster?"
- "Are there any unhealthy pods?"
- "List all services in kube-system"
- "Show YAML for deployment nginx"
- "Which pods are in CrashLoopBackOff?"

**Agent File**: `agents/describe_agent.py`

---

### 3. **Resources Agent** 📊
**Responsibility**: CPU/memory capacity, allocation (requests/limits), and utilization

**No Dedicated MCP Server** - Tools execute directly via kubectl (no separate server process)

**Tools (6)**:
1. **get_node_resources**: Node **capacity** and **allocatable** resources
   - Capacity = Total physical resources on node
   - Allocatable = Available for pods (Capacity - Reserved for system)
2. **get_pod_resources**: Pod resource **requests** and **limits**
3. **get_namespace_resources**: Aggregate resource usage by namespace
4. **get_node_utilization**: Current node CPU/memory **usage** (requires metrics-server)
5. **get_pod_utilization**: Current pod CPU/memory **usage** (requires metrics-server)
6. **get_pod_memory_comparison**: **★ Find pod with highest CPU or memory allocation**
   - Parses JSON, compares CPU/memory across all pods
   - Works WITHOUT metrics-server (uses requests/limits)
   - Returns sorted lists by CPU and memory

**What It Does**:
- Shows **capacity** (total physical resources) vs **allocatable** (available for pods)
- Displays resource **requests** (guaranteed) and **limits** (maximum allowed)
- Compares pods by CPU/memory allocation
- Shows node utilization percentages

**Key Concepts**:
- **Capacity**: Total CPU/memory on node hardware
- **Allocatable**: Capacity minus system reserved resources
- **Requests**: Guaranteed resources for pod (used for scheduling)
- **Limits**: Maximum resources pod can use (enforced at runtime)

**Example Queries**:
- "What's the total allocatable memory in the cluster?"
- "Show resource limits and requests for all pods"
- "Which pod has the highest memory limit?"
- "What's the node capacity vs allocatable?"

**Agent File**: `agents/resources_agent.py`

**Key Feature**: The `get_pod_memory_comparison` tool automatically:
- Parses CPU values (100m, 1, 0.5) to millicores
- Parses memory values (128Mi, 1Gi) to bytes
- Sorts pods by both CPU and memory
- Identifies top consumers by allocation

---

### 4. **Monitor Agent** 📈
**Responsibility**: Real-time metrics, trends, and performance monitoring via Prometheus

**MCP Server**: `http://localhost:8004/mcp`
- Port: 8004
- File: `MCP/mcp_monitor/mcp_monitor_server.py`
- Framework: FastMCP

**Prometheus Backend**: `http://34.59.188.124:9090`
- Metrics collected by node_exporter on cluster nodes
- PromQL queries for custom metric extraction

**Tools (6)**:
1. **query_prometheus_instant**: Execute ANY PromQL query for current/instant values
   - Most flexible - can query any metric
   - Use for: Custom queries, specific metrics, current values
2. **query_prometheus_range**: Execute PromQL query over time period (historical data)
   - Returns time-series data for trend analysis
3. **get_node_metrics**: Pre-built queries for node CPU, memory, disk, network
   - Simplified node monitoring (no PromQL knowledge required)
4. **get_pod_metrics**: Pre-built queries for pod CPU, memory
   - Simplified pod monitoring
5. **get_top_pods_by_resource**: ★ Universal tool for "which pod uses most X" questions
   - Supports 5 resource types: memory, cpu, disk, network_receive, network_transmit
   - Built-in PromQL queries with sort_desc() for ranking
   - Extracts numbers from questions ("top 3" → top_n=3)
   - Returns formatted results with units (MB, %, KB/s)
6. **check_prometheus_targets**: Verify Prometheus is scraping all targets

**What It Does**:
- Queries Prometheus for **real-time** and **historical** metrics
- Shows **actual usage** (not requests/limits - that's Resources Agent)
- Supports trend analysis over time ranges
- Finds top N pods by any resource metric
- Validates Prometheus scraping health

**Difference from Resources Agent**:
| Monitor Agent | Resources Agent |
|---------------|-----------------|
| **Actual usage** from Prometheus | **Allocation** (requests/limits) from kubectl |
| "Which pod is using most CPU **right now**?" | "Which pod has highest CPU **limit**?" |
| Real-time percentages, MB, KB/s | Requests/limits in millicores, Mi/Gi |
| Historical trends ("last hour") | Static configuration values |

**Example Queries**:
- "Which pod is using the most memory right now?"
- "Show me the top 3 pods with highest network traffic"
- "What's the CPU usage trend for the master node over the last hour?"
- "Which 5 pods have the highest disk usage?"
- "Show current memory usage percentage for all nodes"

**Agent File**: `agents/monitor_agent.py`

**Important Notes**:
- Requires Prometheus with node_exporter on cluster nodes
- Some metrics may not be available (e.g., container_fs_usage_bytes for disk)
- Tool #5 (get_top_pods_by_resource) has critical number extraction rules to preserve "top 3", "top 5" from questions

---

### 5. **Operations Agent** ⚙️
**Responsibility**: Write operations - scale, delete, restart, node maintenance

**MCP Server**: `http://localhost:8003/mcp`
- Port: 8003
- File: `MCP/mcp_operations/mcp_operations_server.py`
- Framework: FastMCP

**Tools (15)**:

**Deployment Operations (5)**:
1. **scale_deployment_tool**: Scale deployment to N replicas
2. **restart_deployment_tool**: Rollout restart (recreate pods)
3. **rollback_deployment_tool**: Rollback to previous/specific revision
4. **get_deployment_rollout_status_tool**: Check rollout progress
5. **delete_deployment_tool**: Delete deployment and all its pods

**Pod Operations (3)**:
6. **delete_pod_tool**: Delete a specific pod
7. **delete_pods_by_status_tool**: Delete all pods with status (Failed, Pending, etc.)
8. **delete_pods_by_label_tool**: Delete pods matching label selector

**Node Maintenance (3)**:
9. **cordon_node_tool**: Mark node as unschedulable
10. **uncordon_node_tool**: Mark node as schedulable
11. **drain_node_tool**: Safely evict all pods from node

**Resource Management (4)**:
12. **patch_resource_tool**: Apply JSON patch to any K8s resource
13. **apply_yaml_config_tool**: Create/update resources from YAML
14. **create_namespace_tool**: Create new namespace
15. **delete_namespace_tool**: Delete namespace and all resources

**What It Does**:
- Executes **write operations** that modify cluster state
- Scales workloads up/down
- Performs deployment lifecycle operations (restart, rollback)
- Deletes resources (pods, deployments, namespaces)
- Handles node maintenance safely
- Creates resources from YAML manifests

**Critical Behavior**:
- **Executes by default** (dry_run=False) - operations apply immediately
- Only uses dry_run=True if user explicitly says "dry run", "test", "preview", or "simulate"
- Always confirms destructive operations with user

**Example Queries**:
- "Scale stress-tester deployment to 5 replicas"
- "Restart the nginx deployment"
- "Delete all failed pods"
- "Create a new pod named hello with nginx image"
- "Delete the test-yaml-deployment"
- "Drain the worker node for maintenance"
- "Rollback nginx deployment to previous revision"

**Agent File**: `agents/operations_agent.py`

**Safety Features**:
- Confirmation required for destructive operations
- Graceful handling of force deletions
- Dry run capability when explicitly requested
- Detailed status reporting after operations

---

### 6. **Supervisor Agent** 🎯
**Responsibility**: Query routing, orchestration, and response synthesis

**No MCP Server** - Routes to other 5 agents, doesn't have its own tools

**Capabilities**:
- ✅ **Query classification**: Uses LLM to determine which agents are needed
- ✅ **Sub-question extraction**: Breaks complex queries into agent-specific parts
  - **Critical**: Preserves numbers from questions ("top 3" → keeps 3 in sub-question)
- ✅ **Parallel execution**: Up to 5 agents run simultaneously (~5-6s vs ~25s sequential)
- ✅ **Response synthesis**: Combines agent outputs into coherent answer

**Routing Examples**:
```
"cluster health" → HEALTH (only)
"how many pods" → DESCRIBE (only)  
"highest CPU pod" → RESOURCES (allocation) or MONITOR (actual usage)
"node count + node health" → DESCRIBE + HEALTH (parallel)
"pod count + highest memory + cluster health" → 3 AGENTS (parallel)
```

**Smart Routing Rules**:
- **Pod health/status** → DESCRIBE (not Health!)
- **Node health** → HEALTH
- **CPU/memory comparison (allocation)** → RESOURCES
- **CPU/memory comparison (actual usage)** → MONITOR
- **Listing/counting** → DESCRIBE
- **Write operations** → OPERATIONS
- **Real-time metrics/trends** → MONITOR

**How It Works**:
1. User query arrives
2. Supervisor's LLM classifies into categories (HEALTH, DESCRIBE, RESOURCES, MONITOR, OPERATIONS)
3. Extracts sub-questions for each agent (preserves numbers like "top 3")
4. Executes agents in parallel using ThreadPoolExecutor
5. Each agent summarizes its tool results with LLM
6. Supervisor synthesizes all summaries into final answer

**Agent File**: `agents/k8s_agent.py`
- LLM: Claude 3 Haiku for fast classification
- Execution: Parallel via ThreadPoolExecutor (not async)
- Caching: Workflow cached to avoid recreation

## 🔄 Intelligent Routing Pattern

### How It Works (4-Step Process)

```
┌──────────────────────────────────────────────────────────────────┐
│ USER QUERY: "Check pod count, find highest memory pod,          │
│              and check cluster health"                           │
└──────────────────────────────┬───────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│ STEP 1: SUPERVISOR - Query Classification & Decomposition       │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Claude LLM analyzes query:                                     │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Classification: "DESCRIBE, RESOURCES, HEALTH"              │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  Sub-question extraction:                                       │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ • DESCRIBE  → "how many pods in cluster"                   │ │
│  │ • RESOURCES → "find pod with highest memory"               │ │
│  │ • HEALTH    → "check cluster health"                       │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  Supervisor sends ONLY relevant part to each agent             │
└──────────────────────────────┬───────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│ STEP 2: AGENTS - Parallel Execution with MCP Tools              │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │ DESCRIBE Agent  │  │ RESOURCES Agent │  │  HEALTH Agent   │ │
│  │ (Port 8001)     │  │ (Port 8002)     │  │  (Port 8000)    │ │
│  ├─────────────────┤  ├─────────────────┤  ├─────────────────┤ │
│  │                 │  │                 │  │                 │ │
│  │ Receives:       │  │ Receives:       │  │ Receives:       │ │
│  │ "how many pods" │  │ "find highest   │  │ "check cluster  │ │
│  │                 │  │  memory pod"    │  │  health"        │ │
│  │                 │  │                 │  │                 │ │
│  │ Calls MCP Tool: │  │ Calls MCP Tool: │  │ Calls MCP Tool: │ │
│  │ count_k8s_      │  │ get_pod_memory_ │  │ get_cluster_    │ │
│  │ resources()     │  │ comparison()    │  │ nodes()         │ │
│  │        ↓        │  │        ↓        │  │        ↓        │ │
│  │ Tool Result:    │  │ Tool Result:    │  │ Tool Result:    │ │
│  │ "11 pods"       │  │ "stress-tester: │  │ "2 nodes,       │ │
│  │                 │  │  2048Mi limit"  │  │  both Ready"    │ │
│  │        ↓        │  │        ↓        │  │        ↓        │ │
│  │ Agent's LLM     │  │ Agent's LLM     │  │ Agent's LLM     │ │
│  │ summarizes:     │  │ summarizes:     │  │ summarizes:     │ │
│  │ "Cluster has    │  │ "Pod with       │  │ "Cluster is     │ │
│  │  11 pods across │  │  highest memory │  │  healthy, all   │ │
│  │  3 namespaces"  │  │  is stress-     │  │  nodes Ready"   │ │
│  │                 │  │  tester"        │  │                 │ │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘ │
│           │                    │                     │          │
│           └────────────────────┼─────────────────────┘          │
│                                │                                │
│                    All 3 run in ~6s (parallel)                  │
└────────────────────────────────┬───────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────┐
│ STEP 3: SUPERVISOR - Response Synthesis                         │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Supervisor receives 3 responses:                               │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ • Describe:  "Cluster has 11 pods across 3 namespaces"    │ │
│  │ • Resources: "Pod with highest memory is stress-tester"   │ │
│  │ • Health:    "Cluster is healthy, all nodes Ready"        │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  Supervisor's LLM combines them:                                │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Synthesis Prompt:                                          │ │
│  │ "Combine these responses into coherent answer that:       │ │
│  │  1. Directly answers user's original question             │ │
│  │  2. Removes redundancy                                     │ │
│  │  3. Presents unified cluster view"                         │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
└────────────────────────────────┬─────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────┐
│ STEP 4: FINAL ANSWER to User                                    │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  "Your Kubernetes cluster has 11 pods running across 3          │
│   namespaces. The pod with the highest memory allocation is     │
│   stress-tester-86d895468-86gbm with a 2048Mi limit. The        │
│   cluster is healthy with all nodes in Ready state."            │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### Key Benefits

✅ **No broadcasting**: Each agent gets only its relevant sub-question  
✅ **Parallel execution**: All agents run simultaneously (~6s vs ~18s sequential)  
✅ **Agent-level summarization**: Each agent interprets tool output with LLM  
✅ **Supervisor synthesis**: Final LLM pass creates coherent combined answer  
✅ **Clean separation**: Agents don't know about each other or original question

### Example Routing Scenarios

**Simple Query (1 Agent)**:
```
User: "How many pods?"
└─> Supervisor: DESCRIBE only
    └─> Describe Agent: "how many pods"
        └─> Tool: count_k8s_resources
            └─> Agent LLM: Summarizes
                └─> User: "11 pods"
```

**Complex Query (3 Agents)**:
```
User: "Pod count + highest memory + cluster health"
└─> Supervisor: DESCRIBE + RESOURCES + HEALTH (parallel)
    ├─> Describe:  "pod count"    → Tool → LLM → Summary
    ├─> Resources: "highest mem"  → Tool → LLM → Summary
    └─> Health:    "cluster health" → Tool → LLM → Summary
        └─> Supervisor LLM: Synthesizes all 3 summaries
            └─> User: Combined answer
```

## 🎯 Parallelization Architecture

### MCP Servers

#### **Health MCP Server** (Port 8000)
```python
# File: MCP/mcp_health/mcp_health_server.py
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("K8s-Health")

@mcp.tool()
def get_cluster_nodes() -> str:
    """Get list of all nodes with status"""
    # Executes: kubectl get nodes -o wide
    # Returns: Node list with Ready/NotReady status
```

**Features**:
- FastMCP framework for HTTP transport
- 60-second command caching (`_cached_kubectl_command`)
- Runs independently (can restart without affecting agents)
- StreamableHTTP protocol

**Startup**: Managed by `startup.sh`
```bash
nohup python3 MCP/mcp_health/mcp_health_server.py > mcp_health.log 2>&1 &
```

#### **Describe MCP Server** (Port 8001)
```python
# File: MCP/mcp_describe/mcp_describe_server.py
from mcp.server.fastmcp import FastMCP

# Port configured via FastMCP constructor
port = int(os.getenv('PORT', '8001'))
mcp = FastMCP("K8s-Describe", port=port)

@mcp.tool()
def list_k8s_resources(resource_type: str, namespace: str = "all") -> str:
    """List ANY Kubernetes resource type"""
    # Generic tool - works with all kubectl resources
```

**Features**:
- Same as Health server (FastMCP, caching, HTTP)
- Generic tools (no hardcoded resource types)
- Port set via environment variable in startup.sh

**Startup**: Managed by `startup.sh`
```bash
export PORT=8001
nohup python3 MCP/mcp_describe/mcp_describe_server.py > mcp_describe.log 2>&1 &
```

### Agents

#### **Agent Architecture Pattern** (Both agents follow this)
```python
# 1. Connect to MCP Server
async def _get_mcp_tools():
    client = MultiServerMCPClient({
        "server_name": {
            "transport": "streamable_http",
            "url": "http://127.0.0.1:PORT/mcp"
        }
    })
    return await client.get_tools()

# 2. Create agent with tools
def create_agent():
    tools = asyncio.run(_get_mcp_tools())  # Fetch tools from MCP
    model_with_tools = model.bind_tools(tools)
    # ... LangGraph workflow setup
    
# 3. Async tool execution
async def execute_tools_async():
    for tool_call in tool_calls:
        result = await tool.ainvoke(tool_args)  # MCP requires async
```

**Key Components**:
1. **MCP Client**: `langchain-mcp-adapters.MultiServerMCPClient`
2. **Async execution**: All MCP tools require `ainvoke()` not `invoke()`
3. **Workflow caching**: Global `_cached_workflow` to avoid recreating agent
4. **Error handling**: Graceful degradation if MCP server is down

## Usage Examples

### Single Agent Queries

#### Health Agent
```bash
# Node health
python3 cli.py -q "Are all nodes healthy?"
python3 cli.py -q "Show me node conditions"
python3 cli.py -q "Is there memory pressure on any node?"

# Cluster events
python3 cli.py -q "Any cluster warnings?"
python3 cli.py -q "Show recent cluster events"
python3 cli.py -q "Check control plane health"
```

#### Describe Agent
```bash
# Listing resources
python3 cli.py -q "How many pods in the cluster?"
python3 cli.py -q "List all services in kube-system"
python3 cli.py -q "Show me all deployments"

# Pod health/status (NOT node health!)
python3 cli.py -q "Are there any unhealthy pods?"
python3 cli.py -q "Which pods are failing?"
python3 cli.py -q "Show pods in CrashLoopBackOff"

# Counting
python3 cli.py -q "Count running pods on k8s-master-001"
python3 cli.py -q "How many services are in default namespace?"

# YAML inspection
python3 cli.py -q "Show me the YAML for deployment nginx"
python3 cli.py -q "Get YAML for service kubernetes"
```

#### Resources Agent (Allocation/Requests/Limits)
```bash
# Capacity vs Allocatable
python3 cli.py -q "What's the total allocatable memory in the cluster?"
python3 cli.py -q "Show node capacity and allocatable resources"

# Resource allocation (requests/limits)
python3 cli.py -q "Show resource limits and requests for all pods"
python3 cli.py -q "Which pod has the highest memory limit?"
python3 cli.py -q "Which pods have no memory limits?"

# Finding highest allocated resources
python3 cli.py -q "Which pod has the highest CPU request?"
python3 cli.py -q "Find pod with highest memory allocation"
```

#### Monitor Agent (Actual Usage/Metrics)
```bash
# Real-time metrics (actual usage, not allocation!)
python3 cli.py -q "Which pod is using the most memory right now?"
python3 cli.py -q "Show me the top 3 pods with highest CPU usage"
python3 cli.py -q "Which 5 pods have the highest network receive traffic?"

# Node metrics
python3 cli.py -q "What's the current CPU and memory usage for the master node?"
python3 cli.py -q "Show memory usage percentage for all nodes"

# Historical trends
python3 cli.py -q "Show CPU usage trend for worker node over last hour"
python3 cli.py -q "What was the memory spike in the last 30 minutes?"

# Target health
python3 cli.py -q "Are all Prometheus targets up?"
```

#### Operations Agent (Write Operations)
```bash
# Scaling
python3 cli.py -q "Scale nginx deployment to 3 replicas"
python3 cli.py -q "Scale down stress-tester to 1 replica"

# Deployment operations
python3 cli.py -q "Restart the nginx deployment"
python3 cli.py -q "Rollback nginx to previous revision"

# Pod deletion
python3 cli.py -q "Delete pod hello"
python3 cli.py -q "Delete all failed pods"
python3 cli.py -q "Delete pods with label app=test"

# Deployment deletion
python3 cli.py -q "Delete deployment test-yaml"

# Resource creation
python3 cli.py -q "Create a new pod named hello with nginx image"
python3 cli.py -q "Create deployment named myapp with 2 replicas"

# Node maintenance
python3 cli.py -q "Cordon the worker node"
python3 cli.py -q "Drain worker node for maintenance"
python3 cli.py -q "Uncordon the worker node"

# Namespace operations
python3 cli.py -q "Create namespace dev"
python3 cli.py -q "Delete namespace test"
```

### Multi-Agent Queries (Parallel Execution)
```bash
# All 5 agents can execute simultaneously
python3 cli.py -q "Check pod count, find highest memory pod, check cluster health, show CPU trends, and scale nginx to 3"

# 3 agents (Monitor + Resources + Health)
python3 cli.py -q "Which pod uses most memory now, what's its memory limit, and are nodes healthy?"

# 2 agents (Describe + Health)
python3 cli.py -q "Show all nodes and their health status"

# 2 agents (Resources + Monitor)
python3 cli.py -q "What's the allocatable memory and current memory usage?"
```

### Debug Mode
```bash
# See which sub-questions are sent to each agent
SHOW_ROUTING=1 python3 cli.py -q "your complex query"

# Output:
# 🔧 DEBUG: Describe Agent sub-question: 'how many pods'
# 🔧 DEBUG: Resources Agent sub-question: 'highest memory pod'
# 🔧 DEBUG: Health Agent sub-question: 'cluster health'
```

### Service Management

#### Start All Services
```bash
cd /home/K8s_AI_Project/app2.0
./startup.sh start

# Output:
# - Flask app: http://localhost:7000
# - MCP Health: http://localhost:8000/mcp  
# - MCP Describe: http://localhost:8002/mcp
# - MCP Operations: http://localhost:8003/mcp
# - MCP Monitor: http://localhost:8004/mcp
```

#### Check Status
```bash
./startup.sh status

# Shows:
# - Process IDs
# - Port numbers  
# - Recent logs from each service
```

#### Restart Services
```bash
./startup.sh restart

# Stops all → waits 5s → starts all
```

#### Stop Services
```bash
./startup.sh stop

# Gracefully stops:
# - Flask app
# - MCP Health Server (8000)
# - MCP Describe Server (8002)
# - MCP Operations Server (8003)
# - MCP Monitor Server (8004)
```

## Key Features

✅ **5 Specialized Agents** - Health, Describe, Resources, Monitor, Operations for complete K8s management
✅ **MCP Protocol** - Tools run in separate servers (4 MCP servers on ports 8000, 8002-8004)  
✅ **Parallel Agent Execution** - Up to 5 agents run simultaneously for 5x speedup  
✅ **Smart Sub-Question Extraction** - Each agent receives only relevant query parts (preserves numbers!)
✅ **Natural Language Interface** - Ask questions in plain English  
✅ **Intelligent Routing** - LLM classifies queries and routes to correct agents  
✅ **Pod Health Detection** - Describe Agent checks pod STATUS (Running/Failed/CrashLoopBackOff)  
✅ **Resource Comparison** - Resources Agent finds pods with highest CPU/memory allocation
✅ **Real-Time Metrics** - Monitor Agent queries Prometheus for actual usage/trends
✅ **Write Operations** - Operations Agent scales, deletes, restarts, maintains cluster
✅ **Workflow Caching** - Agents are cached to avoid recreation overhead  
✅ **Command Caching** - 60-second TTL cache for kubectl commands  
✅ **Generic Tools** - Describe agent works with ANY K8s resource type  
✅ **Fast Responses** - Claude Haiku optimized for speed  
✅ **Service Management** - startup.sh manages all servers automatically  
✅ **Debug Mode** - `SHOW_ROUTING=1` shows sub-question routing
✅ **Number Extraction** - Supervisor preserves "top 3", "top 5" in sub-questions
✅ **Dual Resource Querying** - Resources (allocation) vs Monitor (actual usage)

## Why This Architecture?

### Evolution: From Monolith to MCP

**Phase 1: Monolithic Agent** (Initial approach)
```
Single Agent → All tools in memory → Direct kubectl calls
```
- ❌ All tools loaded even if unused
- ❌ Hard to add new functionality
- ❌ No separation of concerns

**Phase 2: Multi-Agent** (Intermediate)
```
Supervisor → Multiple Specialized Agents → Tools directly imported
```
- ✅ Separation of concerns
- ✅ Parallel agent execution
- ❌ Still tightly coupled (agent imports tools directly)
- ❌ Hard to share tools across agents

**Phase 3: MCP Architecture** (Current)
```
Supervisor → Agents → MCP Clients → MCP Servers → Tools
```
- ✅ Complete decoupling (agents don't import tools)
- ✅ Tools run in separate processes
- ✅ Easy to add new agents (just connect to existing server)
- ✅ Server-level caching benefits all agents
- ✅ Can restart servers without restarting agents

### Design Principles

1. **LLM for intent understanding** - What does the user want?
2. **Tools for facts** - Never let LLM guess cluster state
3. **MCP for tool isolation** - Tools are services, not libraries
4. **Parallel execution** - Multiple agents run simultaneously for speed
5. **Caching at multiple levels**:
   - Workflow caching (agents)
   - Command caching (MCP servers, 60s TTL)
6. **Framework-based** - Uses LangGraph + FastMCP (no custom hacks)

## Requirements

- Python 3.10+
- Virtual environment: `.venv` (in app2.0 folder)
- Dependencies:
  - `anthropic` - Claude API
  - `langgraph` - Agent orchestration
  - `langchain` - Core framework
  - `langchain-anthropic` - Claude integration
  - `langchain-mcp-adapters` - MCP client support
  - `mcp[server]` - FastMCP server framework
- Google Cloud access to k8s-master-001 VM
- Kubernetes cluster with kubectl access

## Setup

```bash
# Navigate to app2.0 folder
cd /home/K8s_AI_Project/app2.0

# Activate virtual environment  
source .venv/bin/activate

# Start all services (Flask + 2 MCP servers)
./startup.sh start

# Check services are running
./startup.sh status

# Run queries
python3 cli.py -q "Your question here"

# Stop all services when done
./startup.sh stop
```

## Environment Variables

Required in `.env`:
```
ANTHROPIC_API_KEY=your-claude-api-key
```

## File Structure

```
app2.0/
├── cli.py                          # CLI interface (main entry point)
├── startup.sh                      # Service management (start/stop/status/restart)
├── app.log                         # Flask application logs
├── mcp_health.log                  # Health MCP server logs
├── mcp_describe.log                # Describe MCP server logs
├── mcp_operations.log              # Operations MCP server logs
├── mcp_monitor.log                 # Monitor MCP server logs
├── app.pid                         # Flask process ID
├── mcp_health.pid                  # Health server process ID
├── mcp_describe.pid                # Describe server process ID
├── mcp_operations.pid              # Operations server process ID
├── mcp_monitor.pid                 # Monitor server process ID
│
├── agents/                         # AI Agents (5 total)
│   ├── __init__.py
│   ├── k8s_agent.py                # Supervisor agent (routing + orchestration)
│   ├── health_agent.py             # Health monitoring agent
│   ├── describe_agent.py           # Resource information agent
│   ├── resources_agent.py          # CPU/memory capacity agent
│   ├── monitor_agent.py            # Prometheus metrics agent
│   └── operations_agent.py         # Write operations agent
│
├── MCP/                            # Model Context Protocol Servers (4 total)
│   ├── mcp_health/
│   │   ├── mcp_health_server.py    # Health tools MCP server (port 8000)
│   │   ├── mcp_health_client.py    # Standalone test client
│   │   └── tools_health.py         # Health tools definitions (3 tools)
│   │
│   ├── mcp_describe/
│   │   ├── mcp_describe_server.py  # Describe tools MCP server (port 8002)
│   │   ├── mcp_describe_client.py  # Standalone test client
│   │   └── tools_describe.py       # Describe tools definitions (5 tools)
│   │
│   ├── mcp_operations/
│   │   ├── mcp_operations_server.py # Operations tools MCP server (port 8003)
│   │   ├── mcp_operations_client.py # Standalone test client
│   │   └── tools_operations.py      # Operations tools definitions (15 tools)
│   │
│   └── mcp_monitor/
│       ├── mcp_monitor_server.py   # Monitor tools MCP server (port 8004)
│       ├── mcp_monitor_client.py   # Standalone test client
│       └── tools_monitor.py        # Monitor tools definitions (6 tools)
│
├── .venv/                          # Python virtual environment
├── .env                            # Environment variables (ANTHROPIC_API_KEY)
└── README.md                       # This file
```

### Service Communication Ports
- **Flask App**: 7000 (optional web interface)
- **MCP Health Server**: 8000 (`http://localhost:8000/mcp`)
- **MCP Describe Server**: 8002 (`http://localhost:8002/mcp`)
- **MCP Operations Server**: 8003 (`http://localhost:8003/mcp`)
- **MCP Monitor Server**: 8004 (`http://localhost:8004/mcp`)

**Note**: Port 8001 is skipped (not used)

## Future Enhancements

### Completed Features ✅
- ✅ **Monitor Agent** - Real-time Prometheus metrics and trends
- ✅ **Operations Agent** - Scaling, updates, deletions, node maintenance
- ✅ **get_top_pods_by_resource** - Universal tool for "which pod uses most X" queries
- ✅ **Number extraction** - Supervisor preserves "top 3", "top 5" in sub-questions
- ✅ **delete_deployment** - Direct deployment deletion without pod targeting

### Planned Enhancements
- [ ] **Security Agent** - RBAC, roles, network policies, secrets auditing
- [ ] **Cost Agent** - Resource cost analysis, optimization recommendations
- [ ] **Backup Agent** - YAML backups, disaster recovery

### Architecture Improvements  
- [ ] Add intent router (auto-detect K8s vs general queries)
- [ ] Support multiple clusters (multi-cluster management)
- [ ] Implement tool-level parallelization (within single agent)
- [ ] Add streaming responses for long-running queries
- [ ] Web UI dashboard with real-time updates

### Features
- [ ] Interactive mode (conversational multi-turn queries)
- [ ] Export results to files (JSON, CSV, YAML)
- [ ] Query history and favorites
- [ ] Custom tool creation interface
- [ ] Automated alerting based on metrics thresholds
- [ ] Slack/Teams integration for notifications

## Troubleshooting

### MCP Server Won't Start
```bash
# Check if port is already in use
lsof -i :8000  # Health server
lsof -i :8002  # Describe server
lsof -i :8003  # Operations server
lsof -i :8004  # Monitor server

# Check logs
tail -f mcp_health.log
tail -f mcp_describe.log
tail -f mcp_operations.log
tail -f mcp_monitor.log

# Restart services
./startup.sh restart
```

### Agent Can't Connect to MCP Server
```bash
# Verify servers are running
./startup.sh status

# Test MCP connection manually
cd MCP/mcp_health && python3 mcp_health_client.py
cd MCP/mcp_describe && python3 mcp_describe_client.py
cd MCP/mcp_operations && python3 mcp_operations_client.py
cd MCP/mcp_monitor && python3 mcp_monitor_client.py
```

### Slow Responses
- **Check cache**: 60s TTL may have expired
- **Network**: gcloud SSH connection to GCP VM may be slow
- **Parallel queries**: Use queries that trigger multiple agents for faster combined results

### Wrong Agent Routing
```bash
# Enable debug mode to see routing
SHOW_ROUTING=1 python3 cli.py -q "your query"

# Check sub-questions sent to each agent
# Verify classification is correct
```

## Performance Metrics

| Scenario | Sequential Time | Parallel Time | Speedup |
|----------|----------------|---------------|---------|
| 5 agents (complex query) | ~30s | ~6s | **5x faster** |
| 3 agents (Health+Describe+Resources) | ~18s | ~6s | **3x faster** |
| 2 agents (any combination) | ~12s | ~6s | **2x faster** |
| Single agent (1 tool) | ~5s | ~5s | Same |
| Single agent (3 tools) | ~15s | ~15s | Same (within agent) |

**Cache Impact**: 
- First query: ~6s
- Repeated query (within 60s): ~0.5s (cached at MCP server level)

**Real-World Example**:
Query: "Which pod uses most memory, what's its limit, are nodes healthy, show CPU trends, and scale nginx to 3"
- Sequential: ~30s (5 agents × 6s each)
- Parallel: ~6s (all 5 agents simultaneously)
- **Improvement: 80% faster**

**Note**: Tool-level parallelization (within single agent) is NOT implemented. Sequential execution within agents is intentional to:
- Simplify error handling
- Prevent overwhelming K8s API server  
- Leverage 60s cache for good performance
- Agent-level parallelization provides the main benefit (5x speedup)

---

## Additional Resources

- **LangGraph Documentation**: https://langchain-ai.github.io/langgraph/
- **FastMCP Framework**: https://github.com/jlowin/fastmcp
- **Model Context Protocol**: https://modelcontextprotocol.io/
- **Claude API**: https://docs.anthropic.com/claude/reference/getting-started-with-the-api

---

## Quick Reference

### Agent Capabilities Summary

| Agent | Port | Primary Purpose | Key Tools | Example Query |
|-------|------|----------------|-----------|---------------|
| **Health** | 8000 | Node & cluster health | get_cluster_nodes, describe_node, get_cluster_events | "Are nodes healthy?" |
| **Describe** | 8002 | Resource listing & pod status | list_k8s_resources, count_k8s_resources, get_resource_yaml | "How many pods?" |
| **Resources** | N/A | CPU/memory allocation (requests/limits) | get_node_resources, get_pod_resources, get_pod_memory_comparison | "Which pod has highest memory limit?" |
| **Monitor** | 8004 | Real-time metrics & trends (Prometheus) | query_prometheus, get_node_metrics, get_top_pods_by_resource | "Which pod is using most CPU now?" |
| **Operations** | 8003 | Write operations (scale, delete, restart) | scale_deployment, delete_deployment, apply_yaml_config | "Scale nginx to 3 replicas" |
| **Supervisor** | N/A | Query routing & orchestration | (No tools - routes to other 5 agents) | (Handles all queries) |

### Routing Rules

```
Query Contains                          →  Agent(s)
───────────────────────────────────────────────────────────────────────────
"node health"                           →  HEALTH
"pod health" / "unhealthy" / "failing"  →  DESCRIBE (not Health!)
"highest CPU/memory" + "right now"      →  MONITOR (actual usage)
"highest CPU/memory" + "limit/request"  →  RESOURCES (allocation)
"how many" / "list" / "count"           →  DESCRIBE
"cluster warnings" / "events"           →  HEALTH
"capacity" / "allocatable"              →  RESOURCES
"scale" / "delete" / "restart"          →  OPERATIONS
"usage" / "trend" / "last hour"         →  MONITOR

Complex queries                         →  Multiple agents (parallel)
```

### Monitor vs Resources: When to Use Which?

| Question Type | Agent | Why |
|---------------|-------|-----|
| "Which pod is **using** most memory **right now**?" | Monitor | Real-time **actual usage** from Prometheus |
| "Which pod has highest memory **limit**?" | Resources | Static **allocation** from kubectl |
| "Show me **current CPU usage** for nodes" | Monitor | Real-time metrics (percentages) |
| "What's the **allocatable memory** on nodes?" | Resources | Static capacity configuration |
| "Top 3 pods by **network traffic**" | Monitor | Only Monitor has network metrics |
| "Show **resource requests** for all pods" | Resources | Static allocation/requests |
| "**CPU usage trend** over last hour" | Monitor | Historical time-series data |
| "Which pod has **no memory limits** set?" | Resources | Configuration analysis |

### MCP Servers at a Glance

```
Health Server (8000)          Describe Server (8002)       Operations Server (8003)
├── get_cluster_nodes         ├── list_k8s_resources       ├── scale_deployment_tool
├── describe_node             ├── describe_k8s_resource    ├── restart_deployment_tool
└── get_cluster_events        ├── count_k8s_resources      ├── rollback_deployment_tool
                              ├── get_all_resources        ├── delete_pod_tool
                              └── get_resource_yaml        ├── delete_deployment_tool ★
                                                           ├── cordon_node_tool
Monitor Server (8004)                                      ├── drain_node_tool
├── query_prometheus_instant                               ├── patch_resource_tool
├── query_prometheus_range                                 ├── apply_yaml_config_tool
├── get_node_metrics                                       └── ... (15 tools total)
├── get_pod_metrics
├── get_top_pods_by_resource ★ (5 resource types)
└── check_prometheus_targets

★ = Recently added/enhanced tools
```

---

**Built with**: LangGraph + FastMCP + Claude Haiku + Kubernetes

