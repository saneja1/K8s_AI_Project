# Kubernetes AI Agent - Multi-Agent System with MCP Architecture

A CLI tool that uses AI agents with Model Context Protocol (MCP) servers to query and manage Kubernetes clusters through natural language.

## 🏗️ Architecture Overview (MCP-Based)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USER (CLI)                                     │
│                      python3 cli.py -q "query"                              │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   │ Natural Language Query
                                   │
                    ┌──────────────▼───────────────┐
                    │  K8s Supervisor Agent        │
                    │  (k8s_agent.py)              │
                    │                              │
                    │  • Routes to specialized     │
                    │    agents based on query     │
                    │  • Parallel agent execution  │
                    │  • Claude Haiku (fast)       │
                    └──────────────┬───────────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    │                             │
         ┌──────────▼────────────┐    ┌──────────▼────────────┐
         │   Health Agent        │    │   Describe Agent      │
         │ (health_agent.py)     │    │ (describe_agent.py)   │
         │                       │    │                       │
         │ • Node health status  │    │ • List resources      │
         │ • Cluster events      │    │ • Count resources     │
         │ • Conditions/taints   │    │ • Get YAML            │
         └──────────┬────────────┘    └──────────┬────────────┘
                    │                             │
                    │ MCP Client                  │ MCP Client
                    │ Connection                  │ Connection
                    │                             │
         ┌──────────▼────────────┐    ┌──────────▼────────────┐
         │ MCP Health Server     │    │ MCP Describe Server   │
         │ Port: 8000            │    │ Port: 8001            │
         │ (mcp_health_server.py)│    │ (mcp_describe_server) │
         │                       │    │                       │
         │ Tools (3):            │    │ Tools (5):            │
         │ • get_cluster_nodes   │    │ • list_k8s_resources  │
         │ • describe_node       │    │ • describe_k8s_resource│
         │ • get_cluster_events  │    │ • count_k8s_resources │
         │                       │    │ • get_all_resources   │
         │ FastMCP Framework     │    │ • get_resource_yaml   │
         │ 60s cache TTL         │    │                       │
         └──────────┬────────────┘    │ FastMCP Framework     │
                    │                 │ 60s cache TTL         │
                    │                 └──────────┬────────────┘
                    │                            │
                    └──────────┬─────────────────┘
                               │
                               │ kubectl via gcloud SSH
                               │
                    ┌──────────▼────────────┐
                    │  Google Cloud VM      │
                    │  k8s-master-001       │
                    │                       │
                    │  Kubernetes Cluster   │
                    │  • Master Node        │
                    │  • Worker Nodes       │
                    └───────────────────────┘
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
**Responsibility**: Cluster and node health monitoring

**MCP Server**: `http://localhost:8000/mcp`
- Port: 8000
- File: `MCP/mcp_health/mcp_health_server.py`
- Framework: FastMCP

**Tools (3)**:
1. **get_cluster_nodes**: List all nodes with status (Ready/NotReady)
2. **describe_node**: Detailed node conditions
   - Ready, MemoryPressure, DiskPressure, PIDPressure
   - Taints and cordons
   - Resource capacity
3. **get_cluster_events**: Recent cluster events (warnings, errors)

**Example Queries**:
- "Are all nodes healthy?"
- "Show me node conditions"
- "Any cluster warnings?"
- "Is there memory pressure on any node?"

**Agent File**: `agents/health_agent.py`
- Uses: `langchain-mcp-adapters` for MCP connection
- Async tool execution with `ainvoke()`
- Workflow caching for performance

---

### 2. **Describe Agent** 📝
**Responsibility**: Resource information and discovery

**MCP Server**: `http://localhost:8001/mcp`
- Port: 8001  
- File: `MCP/mcp_describe/mcp_describe_server.py`
- Framework: FastMCP

**Tools (5 Generic Tools)**:
1. **list_k8s_resources**: List ANY resource type
   - Works with: pods, services, deployments, nodes, namespaces, configmaps, secrets, etc.
   - Supports namespace filtering
   
2. **describe_k8s_resource**: Get detailed info about ANY specific resource
   - Auto-matches partial pod names
   - Works with all kubectl-supported resources
   
3. **count_k8s_resources**: Count resources with optional filtering
   - Filter by: status, namespace, node, ready, label
   - Prevents LLM counting errors
   
4. **get_all_resources_in_namespace**: Quick overview
   - Equivalent to: `kubectl get all -n <namespace>`
   - Shows pods, services, deployments, replicasets together
   
5. **get_resource_yaml**: Get YAML definition of any resource
   - Useful for inspecting configurations, labels, annotations

**Example Queries**:
- "How many pods in the cluster?"
- "List all services in kube-system"
- "Show me the YAML for deployment nginx"
- "Count running pods on k8s-master-001"
- "What's in the default namespace?"

**Agent File**: `agents/describe_agent.py`
- Uses: `langchain-mcp-adapters` for MCP connection
- Async tool execution with `ainvoke()`
- Workflow caching for performance

---

### 3. **Supervisor Agent** 🎯
**Responsibility**: Query routing and orchestration

**No MCP Server** - Supervisor doesn't have tools, only routes to other agents

**Capabilities**:
- ✅ **Parallel agent execution**: Multiple agents run simultaneously
- ✅ **Intelligent routing**: Uses Claude to classify queries
- ✅ **Multi-agent queries**: Can call both Health + Describe for comprehensive answers

**Routing Logic**:
```python
"show me all nodes and their health" → DESCRIBE + HEALTH (parallel)
"how many pods are running?" → DESCRIBE (single)
"are nodes healthy?" → HEALTH (single)
```

**Agent File**: `agents/k8s_agent.py`
- Uses: `concurrent.futures.ThreadPoolExecutor` for parallel execution
- LLM: Claude Haiku for fast routing decisions

## 🔄 Query Flow Example

**User Query**: "Show me all nodes and their health status"

```
1. CLI (cli.py)
   └─> Receives query from user

2. Supervisor Agent (k8s_agent.py)
   └─> Classifies query → "DESCRIBE,HEALTH" (both needed)
   └─> Creates two threads for parallel execution

3a. Health Agent Thread                3b. Describe Agent Thread
    └─> Connects to port 8000               └─> Connects to port 8001
    └─> Calls: get_cluster_nodes            └─> Calls: list_k8s_resources('nodes')
    └─> Calls: describe_node('all')         └─> Returns: Node list with specs
    └─> Returns: Detailed health            
                                        
4. Supervisor combines results
   └─> **Health Agent:** "All nodes Ready"
   └─> **Describe Agent:** "2 nodes: k8s-master-001, k8s-worker-01..."

5. CLI displays formatted output
```

**Total time**: ~6 seconds (parallel execution)
**vs Sequential**: Would take ~12 seconds

## 🎯 Parallelization Architecture

### **Level 1: Agent-Level Parallelization** ✅ IMPLEMENTED
Multiple agents execute simultaneously:
```python
# Both agents run at the same time
with ThreadPoolExecutor(max_workers=2) as executor:
    health_future = executor.submit(ask_health_agent, query)
    describe_future = executor.submit(ask_describe_agent, query)
```

### **Level 2: Tool-Level Parallelization** ⏸️ NOT IMPLEMENTED
Within a single agent, tools execute sequentially:
```python
# Tools run one after another
for tool_call in tool_calls:
    result = await tool.ainvoke(args)  # Sequential
```

**Why sequential?**
- Simpler error handling
- Prevents overwhelming K8s API server
- 60-second cache already provides good performance
- Agent-level parallelization provides main benefit

## Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     QUERY FLOW                                  │
└─────────────────────────────────────────────────────────────────┘

USER QUERY: "How many pods are running on master node?"
     │
     ▼
┌─────────────────────────────────────────────────┐
│ 1. CLI receives query                           │
│    - Parses arguments                           │
│    - Calls query_cluster()                      │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│ 2. Supervisor Agent receives query              │
│    - Creates LangGraph workflow                 │
│    - Sends query to Claude Haiku LLM            │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│ 3. Claude Haiku analyzes query                  │
│    - Question: "How many pods on master?"       │
│    - Decision: Need to count pods on node       │
│    - Tool Selection: count_pods_on_node()       │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│ 4. Tool executes                                │
│    - SSH to Google Cloud VM                     │
│    - Run: kubectl get pods -A -o wide           │
│    - Count occurrences of "k8s-master-001"      │
│    - Result: 8 pods found                       │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│ 5. LLM generates final answer                   │
│    - Receives tool output                       │
│    - Formats response                           │
│    - "There are 8 pods on the master node."     │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│ 6. CLI displays result                          │
│    ════════════════════════════════════════     │
│    There are 8 pods on the master node.         │
│    ════════════════════════════════════════     │
└─────────────────────────────────────────────────┘
```

## Component Details

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

# Counting
python3 cli.py -q "Count running pods on k8s-master-001"
python3 cli.py -q "How many services are in default namespace?"

# YAML inspection
python3 cli.py -q "Show me the YAML for deployment nginx"
python3 cli.py -q "Get YAML for service kubernetes"
```

### Multi-Agent Queries (Parallel Execution)
```bash
# Both Health + Describe agents execute simultaneously
python3 cli.py -q "Show me all nodes and their health status"
python3 cli.py -q "List all pods with their node health"
python3 cli.py -q "What's the cluster status and resource overview?"
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
```

## Key Features

✅ **Multi-Agent Architecture** - Specialized agents for different concerns  
✅ **MCP Protocol** - Tools run in separate servers for better scalability  
✅ **Parallel Agent Execution** - Multiple agents run simultaneously  
✅ **Natural Language Interface** - Ask questions in plain English  
✅ **Smart Tool Selection** - LLM chooses the right tool automatically  
✅ **Workflow Caching** - Agents are cached to avoid recreation overhead  
✅ **Command Caching** - 60-second TTL cache for kubectl commands  
✅ **Generic Tools** - Describe agent works with ANY K8s resource type  
✅ **Fast Responses** - Claude Haiku optimized for speed  
✅ **Service Management** - startup.sh manages all servers automatically

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
├── app.pid                         # Flask process ID
├── mcp_health.pid                  # Health server process ID
├── mcp_describe.pid                # Describe server process ID
│
├── agents/                         # AI Agents
│   ├── __init__.py
│   ├── k8s_agent.py                # Supervisor agent (routing + parallel execution)
│   ├── health_agent.py             # Health monitoring agent
│   └── describe_agent.py           # Resource information agent
│
├── MCP/                            # Model Context Protocol Servers
│   ├── mcp_health/
│   │   ├── mcp_health_server.py    # Health tools MCP server (port 8000)
│   │   ├── mcp_health_client.py    # Standalone test client
│   │   └── tools_health.py         # Health tools definitions
│   │
│   └── mcp_describe/
│       ├── mcp_describe_server.py  # Describe tools MCP server (port 8001)
│       ├── mcp_describe_client.py  # Standalone test client
│       └── tools_describe.py       # Describe tools definitions
│
├── .venv/                          # Python virtual environment
├── .env                            # Environment variables (ANTHROPIC_API_KEY)
└── README.md                       # This file
```

### Service Communication Ports
- **Flask App**: 7000 (optional web interface)
- **MCP Health Server**: 8000 (`http://localhost:8000/mcp`)
- **MCP Describe Server**: 8001 (`http://localhost:8001/mcp`)

## Future Enhancements

### Planned Agents
- [ ] **Resources Agent** - CPU/memory capacity and usage monitoring
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

## Troubleshooting

### MCP Server Won't Start
```bash
# Check if port is already in use
lsof -i :8000  # Health server
lsof -i :8001  # Describe server

# Check logs
tail -f mcp_health.log
tail -f mcp_describe.log

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
```

### Slow Responses
- **Check cache**: 60s TTL may have expired
- **Network**: gcloud SSH connection to GCP VM may be slow
- **Parallel queries**: Use queries that trigger multiple agents for faster combined results

## Performance Metrics

| Scenario | Time (Single Agent) | Time (Parallel) | Improvement |
|----------|-------------------|-----------------|-------------|
| Node list + health | ~12s (sequential) | ~6s | 2x faster |
| Simple query (1 tool) | ~5s | ~5s | Same |
| Complex (3 tools) | ~15s | ~15s | Same (within agent) |

**Cache Impact**: Repeated queries within 60s: ~0.5s (cached)

---

## Additional Resources

- **LangGraph Documentation**: https://langchain-ai.github.io/langgraph/
- **FastMCP Framework**: https://github.com/jlowin/fastmcp
- **Model Context Protocol**: https://modelcontextprotocol.io/
- **Claude API**: https://docs.anthropic.com/claude/reference/getting-started-with-the-api

---

**Built with**: LangGraph + FastMCP + Claude Haiku + Kubernetes
