# Kubernetes AI Agent - Multi-Agent System with MCP Architecture

A CLI tool that uses AI agents with Model Context Protocol (MCP) servers to query and manage Kubernetes clusters through natural language.

## 🏗️ Architecture Overview (MCP-Based)

```
┌──────────────────────────────────────────────────────────────────────┐
│                         USER (CLI Interface)                         │
│                   python cli.py -q "your question"                   │
└────────────────────────────────┬─────────────────────────────────────┘
                                 │
                                 │ Natural Language Query
                                 ▼
                  ┌──────────────────────────────────┐
                  │   Kubernetes Supervisor Agent    │
                  │        (k8s_agent.py)            │
                  │                                  │
                  │  • Query classification (LLM)    │
                  │  • Sub-question extraction       │
                  │  • Parallel agent execution      │
                  │  • Response synthesis            │
                  │  • Claude 3 Haiku (fast)         │
                  └──────────────┬───────────────────┘
                                 │
             ┌───────────────────┼───────────────────┐
             │                   │                   │
    ┌────────▼────────┐  ┌──────▼───────┐  ┌───────▼────────┐
    │  Health Agent   │  │ Describe     │  │  Resources     │
    │ health_agent.py │  │ Agent        │  │  Agent         │
    │                 │  │ describe_    │  │ resources_     │
    │ Node health,    │  │ agent.py     │  │ agent.py       │
    │ cluster events, │  │              │  │                │
    │ control plane   │  │ List/count   │  │ CPU/memory     │
    │                 │  │ resources,   │  │ capacity,      │
    │                 │  │ pod status   │  │ utilization    │
    └────────┬────────┘  └──────┬───────┘  └───────┬────────┘
             │                  │                   │
             │ MCP Client       │ MCP Client        │ MCP Client
             │ (HTTP)           │ (HTTP)            │ (HTTP)
             ▼                  ▼                   ▼
    ┌─────────────────┐ ┌──────────────────┐ ┌─────────────────┐
    │  MCP Health     │ │  MCP Describe    │ │ MCP Resources   │
    │  Server         │ │  Server          │ │ Server          │
    │  Port: 8000     │ │  Port: 8001      │ │ Port: 8002      │
    │                 │ │                  │ │                 │
    │ Tools (3):      │ │ Tools (5):       │ │ Tools (6):      │
    │ • nodes list    │ │ • list resources │ │ • node capacity │
    │ • node describe │ │ • describe K8s   │ │ • pod limits    │
    │ • cluster events│ │ • count resources│ │ • namespace agg │
    │                 │ │ • get all        │ │ • node usage    │
    │                 │ │ • get YAML       │ │ • pod usage     │
    │                 │ │                  │ │ • CPU/mem compare│
    └────────┬────────┘ └──────┬───────────┘ └───────┬─────────┘
             │                 │                      │
             │                 │ kubectl via SSH      │
             └─────────────────┼──────────────────────┘
                               ▼
                  ┌─────────────────────────┐
                  │  Google Cloud VM        │
                  │  k8s-master-001         │
                  │                         │
                  │  Kubernetes Cluster     │
                  │  • Master + Workers     │
                  └─────────────────────────┘
```

## 🚀 What is MCP (Model Context Protocol)?

**MCP** is a protocol that allows AI agents to connect to external tool servers. Think of it as a standardized way for AI agents to access tools.

### Why MCP Architecture?

**Traditional Approach** (what we moved away from):
```
Agent → Direct tool imports → Tools in same process
```
- ❌ All tools loaded in memory even if unused
- ❌ Hard to share tools across multiple agents
- ❌ Difficult to scale

**MCP Approach** (current architecture):
```
Agent → MCP Client → HTTP → MCP Server → Tools
```
- ✅ Tools run in separate processes (better isolation)
- ✅ Multiple agents can share same MCP server
- ✅ Tools loaded only when needed
- ✅ Can cache results at server level (60s TTL)
- ✅ Easier to add new agents (just connect to existing servers)

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

**Example Queries**:
- "Are all nodes healthy?"
- "Is there memory pressure?"
- "Show cluster warnings"

**Agent File**: `agents/health_agent.py`

---

### 2. **Describe Agent** 📝
**Responsibility**: Resource discovery and pod status

**MCP Server**: `http://localhost:8001/mcp`
- Port: 8001
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
- **Note**: Pod health belongs to Describe, not Health Agent

**Example Queries**:
- "How many pods in the cluster?"
- "Are there any unhealthy pods?"
- "List all services"
- "Show YAML for deployment nginx"

**Agent File**: `agents/describe_agent.py`

---

### 3. **Resources Agent** 📊
**Responsibility**: CPU/memory capacity, allocation, and utilization

**MCP Server**: `http://localhost:8002/mcp`
- Port: 8002
- File: `MCP/mcp_resources/mcp_resources_server.py`
- Framework: FastMCP

**Tools (6)**:
1. **get_node_resources**: Node capacity and allocatable resources (CPU, memory, storage)
2. **get_pod_resources**: Pod resource requests and limits
3. **get_namespace_resources**: Aggregate resource usage by namespace
4. **get_node_utilization**: Current node CPU/memory usage (requires metrics-server)
5. **get_pod_utilization**: Current pod CPU/memory usage (requires metrics-server)
6. **get_pod_memory_comparison**: **★ Find pod with highest CPU or memory allocation**
   - Parses JSON, compares CPU/memory across all pods
   - Works WITHOUT metrics-server (uses requests/limits)
   - Returns sorted lists by CPU and memory

**Example Queries**:
- "What's the memory capacity on nodes?"
- "Which pod uses most CPU?"
- "Find pod with highest memory"
- "Show resource limits for all pods"

**Agent File**: `agents/resources_agent.py`

**Key Feature**: The `get_pod_memory_comparison` tool automatically:
- Parses CPU values (100m, 1, 0.5) to millicores
- Parses memory values (128Mi, 1Gi) to bytes
- Sorts pods by both CPU and memory
- Identifies winners for each category

---

### 4. **Supervisor Agent** 🎯
**Responsibility**: Query routing and multi-agent orchestration

**No MCP Server** - Routes to other agents, doesn't have its own tools

**Capabilities**:
- ✅ **Query classification**: Uses LLM to determine which agents are needed
- ✅ **Sub-question extraction**: Breaks complex queries into agent-specific parts
- ✅ **Parallel execution**: Multiple agents run simultaneously
- ✅ **Response synthesis**: Combines agent outputs into coherent answer

**Routing Examples**:
```
"cluster health" → HEALTH (only)
"how many pods" → DESCRIBE (only)  
"highest CPU pod" → RESOURCES (only)
"node count + node health" → DESCRIBE + HEALTH (parallel)
"pod count + highest memory + cluster health" → ALL 3 AGENTS (parallel)
```

**Smart Routing Rules**:
- **Pod health/status** → DESCRIBE (not Health!)
- **Node health** → HEALTH
- **CPU/memory comparison** → RESOURCES
- **Listing/counting** → DESCRIBE

**Agent File**: `agents/k8s_agent.py`
- LLM: Claude 3 Haiku for fast classification

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
python3 cli.py -q "Is there memory pressure?"

# Cluster events
python3 cli.py -q "Any cluster warnings?"
python3 cli.py -q "Show recent cluster events"
```

#### Describe Agent
```bash
# Listing resources
python3 cli.py -q "How many pods in the cluster?"
python3 cli.py -q "List all services in kube-system"
python3 cli.py -q "Show me all deployments"

# Pod health/status
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

#### Resources Agent
```bash
# Capacity
python3 cli.py -q "What's the memory capacity on nodes?"
python3 cli.py -q "Show node resource allocation"

# Finding highest resource consumers
python3 cli.py -q "Which pod uses most CPU?"
python3 cli.py -q "Find pod with highest memory"
python3 cli.py -q "Show me top 5 memory consumers"

# Resource limits/requests
python3 cli.py -q "Show resource limits for all pods"
python3 cli.py -q "Which pods have no memory limits?"
```

### Multi-Agent Queries (Parallel Execution)
```bash
# All 3 agents execute simultaneously
python3 cli.py -q "Check pod count, find highest memory pod, and check cluster health"
python3 cli.py -q "List pods in default, which uses most CPU, are there unhealthy pods"

# 2 agents
python3 cli.py -q "Show all nodes and their health status"
python3 cli.py -q "How many pods and what's the cluster health?"
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
# - MCP Describe: http://localhost:8001/mcp
# - MCP Resources: http://localhost:8002/mcp
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
# - MCP Health Server
# - MCP Describe Server
# - MCP Resources Server
```

## Key Features

✅ **3 Specialized Agents** - Health, Describe, Resources for separation of concerns  
✅ **MCP Protocol** - Tools run in separate servers for better scalability  
✅ **Parallel Agent Execution** - Multiple agents run simultaneously for 3x speedup  
✅ **Smart Sub-Question Extraction** - Each agent receives only relevant query parts  
✅ **Natural Language Interface** - Ask questions in plain English  
✅ **Intelligent Routing** - LLM classifies queries and routes to correct agents  
✅ **Pod Health Detection** - Describe Agent checks pod STATUS (Running/Failed/CrashLoopBackOff)  
✅ **Resource Comparison** - Resources Agent finds pods with highest CPU/memory  
✅ **Workflow Caching** - Agents are cached to avoid recreation overhead  
✅ **Command Caching** - 60-second TTL cache for kubectl commands  
✅ **Generic Tools** - Describe agent works with ANY K8s resource type  
✅ **Fast Responses** - Claude Haiku optimized for speed  
✅ **Service Management** - startup.sh manages all servers automatically  
✅ **Debug Mode** - `SHOW_ROUTING=1` shows sub-question routing

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
├── mcp_resources.log               # Resources MCP server logs
├── app.pid                         # Flask process ID
├── mcp_health.pid                  # Health server process ID
├── mcp_describe.pid                # Describe server process ID
├── mcp_resources.pid               # Resources server process ID
│
├── agents/                         # AI Agents
│   ├── __init__.py
│   ├── k8s_agent.py                # Supervisor agent (routing + orchestration)
│   ├── health_agent.py             # Health monitoring agent
│   ├── describe_agent.py           # Resource information agent
│   └── resources_agent.py          # CPU/memory capacity agent
│
├── MCP/                            # Model Context Protocol Servers
│   ├── mcp_health/
│   │   ├── mcp_health_server.py    # Health tools MCP server (port 8000)
│   │   ├── mcp_health_client.py    # Standalone test client
│   │   └── tools_health.py         # Health tools definitions
│   │
│   ├── mcp_describe/
│   │   ├── mcp_describe_server.py  # Describe tools MCP server (port 8001)
│   │   ├── mcp_describe_client.py  # Standalone test client
│   │   └── tools_describe.py       # Describe tools definitions
│   │
│   └── mcp_resources/
│       ├── mcp_resources_server.py # Resources tools MCP server (port 8002)
│       ├── mcp_resources_client.py # Standalone test client
│       └── tools_resources.py      # Resources tools definitions
│
├── .venv/                          # Python virtual environment
├── .env                            # Environment variables (ANTHROPIC_API_KEY)
└── README.md                       # This file
```

### Service Communication Ports
- **Flask App**: 7000 (optional web interface)
- **MCP Health Server**: 8000 (`http://localhost:8000/mcp`)
- **MCP Describe Server**: 8001 (`http://localhost:8001/mcp`)
- **MCP Resources Server**: 8002 (`http://localhost:8002/mcp`)

## Future Enhancements

### Planned Agents
- [ ] **Monitor Agent** - Performance metrics and trends over time
- [ ] **Security Agent** - RBAC, roles, network policies, secrets
- [ ] **Operations Agent** - Scaling, updates, rollouts, maintenance

### Architecture Improvements  
- [ ] Add intent router (auto-detect K8s vs general queries)
- [ ] Support multiple clusters (multi-cluster management)
- [ ] Implement tool-level parallelization (within single agent)
- [ ] Add streaming responses for long-running queries
- [ ] Web UI dashboard (currently CLI-only)

### Features
- [ ] Interactive mode (conversational multi-turn queries)
- [ ] Export results to files (JSON, CSV, YAML)
- [ ] Query history and favorites
- [ ] Custom tool creation interface
- [ ] Metrics-server integration for real-time usage data

## Troubleshooting

### MCP Server Won't Start
```bash
# Check if port is already in use
lsof -i :8000  # Health server
lsof -i :8001  # Describe server
lsof -i :8002  # Resources server

# Check logs
tail -f mcp_health.log
tail -f mcp_describe.log
tail -f mcp_resources.log

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
cd MCP/mcp_resources && python3 mcp_resources_client.py
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
| 3 agents (complex query) | ~18s | ~6s | **3x faster** |
| 2 agents (Health + Describe) | ~12s | ~6s | **2x faster** |
| Single agent (1 tool) | ~5s | ~5s | Same |
| Single agent (3 tools) | ~15s | ~15s | Same (within agent) |

**Cache Impact**: 
- First query: ~6s
- Repeated query (within 60s): ~0.5s (cached at MCP server level)

**Note**: Tool-level parallelization (within single agent) is NOT implemented. Sequential execution within agents is intentional to:
- Simplify error handling
- Prevent overwhelming K8s API server
- Leverage 60s cache for good performance
- Agent-level parallelization provides the main benefit

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
| **Describe** | 8001 | Resource listing & pod status | list_k8s_resources, count_k8s_resources, get_resource_yaml | "How many pods?" |
| **Resources** | 8002 | CPU/memory capacity & usage | get_node_resources, get_pod_memory_comparison | "Which pod uses most CPU?" |
| **Supervisor** | N/A | Query routing & orchestration | (No tools - routes to other agents) | (Handles all queries) |

### Routing Rules

```
Query Contains              →  Agent(s)
─────────────────────────────────────────────────────
"node health"               →  HEALTH
"pod health" / "unhealthy"  →  DESCRIBE (not Health!)
"highest CPU/memory"        →  RESOURCES
"how many" / "list"         →  DESCRIBE
"cluster warnings"          →  HEALTH
"resource capacity"         →  RESOURCES

Complex queries             →  Multiple agents (parallel)
```

### MCP Servers at a Glance

```
Health Server (8000)          Describe Server (8001)       Resources Server (8002)
├── get_cluster_nodes         ├── list_k8s_resources       ├── get_node_resources
├── describe_node             ├── describe_k8s_resource    ├── get_pod_resources
└── get_cluster_events        ├── count_k8s_resources      ├── get_namespace_resources
                              ├── get_all_resources        ├── get_node_utilization
                              └── get_resource_yaml        ├── get_pod_utilization
                                                           └── get_pod_memory_comparison ★
```

---

**Built with**: LangGraph + FastMCP + Claude Haiku + Kubernetes

