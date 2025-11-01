# Kubernetes AI Agent - CLI Application

A CLI tool that uses an AI supervisor agent to query and manage Kubernetes clusters through natural language.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER (You)                              │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                │ Natural Language Query
                                │ "How many pods on master?"
                                │
                    ┌───────────▼──────────┐
                    │                      │
                    │    cli.py (CLI)      │
                    │                      │
                    │  - Argument Parser   │
                    │  - Simple Interface  │
                    │                      │
                    └───────────┬──────────┘
                                │
                                │ query_cluster()
                                │
        ┌───────────────────────▼───────────────────────┐
        │                                                │
        │      K8s Supervisor Agent (k8s_agent.py)      │
        │                                                │
        │  ┌──────────────────────────────────────┐    │
        │  │   Claude Haiku LLM (Brain)           │    │
        │  │   - Understands questions            │    │
        │  │   - Decides which tools to use       │    │
        │  │   - Generates final answers          │    │
        │  └──────────────┬───────────────────────┘    │
        │                 │                             │
        │                 │ Tool Selection              │
        │                 │                             │
        │  ┌──────────────▼───────────────────────┐    │
        │  │                                       │    │
        │  │      8 Kubernetes Tools               │    │
        │  │      (k8s_tools.py)                   │    │
        │  │                                       │    │
        │  │  1. get_cluster_pods                  │    │
        │  │  2. get_cluster_nodes                 │    │
        │  │  3. describe_node                     │    │
        │  │  4. describe_pod                      │    │
        │  │  5. get_pod_logs (smart name match)   │    │
        │  │  6. get_cluster_events                │    │
        │  │  7. count_pods_on_node                │    │
        │  │  8. count_resources (flexible)        │    │
        │  │                                       │    │
        │  └──────────────┬───────────────────────┘    │
        │                 │                             │
        └─────────────────┼─────────────────────────────┘
                          │
                          │ kubectl commands via SSH
                          │
          ┌───────────────▼────────────────┐
          │                                │
          │   Google Cloud VM              │
          │   (k8s-master-001)             │
          │                                │
          │   ┌────────────────────────┐   │
          │   │  Kubernetes Cluster    │   │
          │   │  - Master Node (8 pods)│   │
          │   │  - Worker Node (3 pods)│   │
          │   └────────────────────────┘   │
          │                                │
          └────────────────────────────────┘
```

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

### 1. CLI (`cli.py`)
- **Purpose**: Simple command-line interface for users
- **Functionality**: 
  - Parses `-q` argument for queries
  - Calls the supervisor agent
  - Displays formatted results
- **No LLM at this level** - just passes queries through

### 2. Supervisor Agent (`agents/k8s_agent.py`)
- **LLM**: Claude Haiku (fast, cost-effective)
- **Framework**: LangGraph (state management + tool orchestration)
- **Responsibilities**:
  - Understand natural language queries
  - Decide which tools to call
  - Chain multiple tool calls if needed
  - Generate human-readable answers
- **System Prompt**: Enforces tool usage for cluster facts (no guessing)

### 3. Tools (`agents/k8s_tools.py`)
All tools execute kubectl commands via SSH to Google Cloud VM.

#### Basic Query Tools:
- `get_cluster_pods`: List all pods with node locations
- `get_cluster_nodes`: Show node status and info
- `describe_node`: Detailed node info (taints, capacity, labels)
- `describe_pod`: Detailed pod information

#### Smart Tools:
- `get_pod_logs`: **Improved** - finds full pod name from partial match
  - Example: "etcd" → finds "etcd-k8s-master-001.us-central1-a..."
- `get_cluster_events`: Show recent cluster events

#### Counting Tools (Fix LLM counting errors):
- `count_pods_on_node`: Count pods on specific node
  - **Why needed**: LLM was miscounting pods (said 6, actual was 8)
  - **Solution**: Direct string matching in kubectl output
  
- `count_resources`: Flexible counting for any resource
  - Can filter by: status, namespace, node, ready state
  - Works with: pods, nodes, services, deployments
  - Example: Count running pods, pods in namespace, etc.

### 4. Kubernetes Cluster
- **Location**: Google Cloud VM (k8s-master-001)
- **Access**: SSH with gcloud CLI
- **Nodes**: 
  - Master: 8 pods (control plane + system)
  - Worker: 3 pods (applications + daemonsets)

## Usage Examples

### Basic Queries
```bash
# List pods
python cli.py -q "Show me all pod names"

# Node information
python cli.py -q "Show cluster nodes"

# Counting
python cli.py -q "How many pods are in the cluster?"
python cli.py -q "How many pods are on master node?"
python cli.py -q "How many running pods in kube-system namespace?"
```

### Logs
```bash
# Smart pod name matching (no need for full name)
python cli.py -q "Show me recent logs from etcd"
python cli.py -q "Show me the last 10 lines of logs for coredns"
```

### Node Details
```bash
python cli.py -q "Which node has more capacity?"
python cli.py -q "Are there taints on master node?"
```

### Events
```bash
python cli.py -q "What are recent cluster events?"
```

## Key Features

✅ **Natural Language Interface** - Ask questions in plain English
✅ **Smart Tool Selection** - LLM chooses the right tool automatically  
✅ **Accurate Counting** - Dedicated counting tools prevent LLM errors
✅ **Partial Name Matching** - No need to type full pod names
✅ **Fast Responses** - Claude Haiku optimized for speed
✅ **Caching** - 30-second TTL cache for repeated queries

## Why This Architecture?

### Problem: LLMs Can't Count Reliably
- Initial approach: LLM parses kubectl output and counts
- **Issue**: LLM miscounted (reported 6 pods, actual was 8)
- **Solution**: Created dedicated counting tools that do exact string matching

### Problem: Long Pod Names
- Kubernetes generates very long pod names with cluster domain
- Example: `etcd-k8s-master-001.us-central1-a.c.beaming-age-463822-k7.internal`
- **Solution**: Tools now auto-detect full names from partial matches

### Design Principles
1. **LLM for intent understanding** - What does the user want?
2. **Tools for facts** - Never let LLM guess cluster state
3. **Simple CLI** - Hide complexity from users
4. **Framework-based** - No custom/hacky solutions (uses LangGraph standard patterns)

## Requirements

- Python 3.8+
- Virtual environment: `.venv`
- Dependencies: `anthropic`, `langgraph`, `langchain`, `langchain-anthropic`
- Google Cloud access to k8s-master-001 VM
- Kubernetes cluster with kubectl access

## Setup

```bash
# Activate virtual environment
cd /home/K8s_AI_Project/app2.0
source .venv/bin/activate

# Run queries
python cli.py -q "Your question here"
```

## Environment Variables

Required in `.env`:
```
ANTHROPIC_API_KEY=your-claude-api-key
```

## File Structure

```
app2.0/
├── cli.py                    # CLI interface (you interact here)
├── agents/
│   ├── __init__.py
│   ├── k8s_agent.py          # Supervisor agent with LLM
│   └── k8s_tools.py          # 8 kubectl tools
├── .venv/                    # Python virtual environment
└── README.md                 # This file
```

## Future Enhancements

- [ ] Add intent router (auto-detect K8s vs general queries)
- [ ] Support multiple clusters
- [ ] Add deployment/scaling capabilities
- [ ] Interactive mode (conversational)
- [ ] Export results to files

## How the LLM Knows Which Tool to Call

### Quick Overview
The supervisor agent uses Claude's **function calling** capability. Here's how it works:

1. **Tools are bound to Claude** with their names, descriptions, and parameters
   ```python
   model_with_tools = model.bind_tools(tools)  # 8 tools registered
   ```

2. **Each tool has a docstring** that Claude reads:
   ```python
   @tool
   def count_pods_on_node(node_name: str) -> str:
       """Count how many pods are running on a specific node."""
   ```

3. **System prompt provides instructions** with examples:
   ```
   User: "how many pods on master?" 
     → Call count_pods_on_node(node_name='k8s-master-001')
   ```

4. **Claude matches user intent to tools**:
   - Sees "how many" → looks for counting tools
   - Sees "pods on master" → needs node-specific count
   - Finds `count_pods_on_node` matches the need
   - Outputs structured tool call with parameters

5. **LangGraph executes the tool** and returns results to Claude

6. **Claude generates final human-readable answer**

### Decision Flow
```
User: "How many pods on master?"
       ↓
Claude analyzes → "Need to count pods on a specific node"
       ↓
Claude checks available tools → Finds count_pods_on_node
       ↓
Claude outputs → tool_call: count_pods_on_node(node_name='k8s-master-001')
       ↓
Tool executes → Returns: "Count: 8 pods..."
       ↓
Claude responds → "There are 8 pods on the master node."
```

**Key Point**: Claude is trained by Anthropic to understand function signatures and automatically output structured tool calls instead of just text when tools are available. The system prompt + tool descriptions guide which tool to use for each scenario.
