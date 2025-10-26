# 🤖 Kubernetes Multi-Agent System

This directory contains a **supervisor-based multi-agent architecture** for intelligent Kubernetes cluster management. The system follows the same pattern as `sample/multiagent_sample.py` but specialized for K8s operations.

---

## 📁 Directory Structure

```
agents/
├── __init__.py              # Package exports and quick start
├── tools.py                 # Tool organization by agent domain
├── supervisor_agent.py      # Main supervisor that routes requests
├── health_agent.py          # Node and cluster health monitoring
├── security_agent.py        # Security policies and RBAC (placeholder)
├── resources_agent.py       # CPU/memory monitoring (placeholder)
├── monitor_agent.py         # Logs, events, and troubleshooting
└── describe_get_agent.py    # Resource listing and description
```

---

## 🎯 Architecture Overview

```
USER QUESTION
     ↓
SUPERVISOR AGENT (Intelligent Router)
     ↓
     ├─→ HEALTH AGENT       → check_node_health, check_cluster_health
     ├─→ SECURITY AGENT     → (placeholder - no tools yet)
     ├─→ RESOURCES AGENT    → (placeholder - no tools yet)
     ├─→ MONITOR AGENT      → get_pod_logs
     └─→ DESCRIBE-GET AGENT → get_cluster_resources, describe_resource
     ↓
FINAL ANSWER (Supervisor synthesizes results)
```

---

## 🚀 Quick Start

### **Option 1: Use the Convenience Function (Recommended)**

```python
from langchain_google_genai import ChatGoogleGenerativeAI
from agents import create_k8s_multiagent_system

# Initialize LLM
llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash-exp",
    temperature=0.2,
    google_api_key="your-api-key"
)

# Create entire multi-agent system
app = create_k8s_multiagent_system(llm)

# Ask questions
result = app.invoke({
    "messages": [
        {"role": "user", "content": "Are all nodes healthy?"}
    ]
})

# Print conversation flow
for msg in result["messages"]:
    msg.pretty_print()

# Get final answer
print(result["messages"][-1].content)
```

### **Option 2: Create Agents Individually (Advanced)**

```python
from langchain_google_genai import ChatGoogleGenerativeAI
from agents import (
    create_k8s_supervisor,
    create_health_agent,
    create_security_agent,
    create_resources_agent,
    create_monitor_agent,
    create_describe_get_agent
)

llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-exp", temperature=0.2)

# Create specialist agents
health_agent = create_health_agent(llm, verbose=False)
security_agent = create_security_agent(llm, verbose=False)
resources_agent = create_resources_agent(llm, verbose=False)
monitor_agent = create_monitor_agent(llm, verbose=False)
describe_get_agent = create_describe_get_agent(llm, verbose=False)

# Create supervisor
workflow = create_k8s_supervisor(
    llm_model=llm,
    health_agent=health_agent,
    security_agent=security_agent,
    resources_agent=resources_agent,
    monitor_agent=monitor_agent,
    describe_get_agent=describe_get_agent,
    verbose=True  # Show routing decisions
)

# Compile and run
app = workflow.compile()
result = app.invoke({"messages": [{"role": "user", "content": "Check cluster"}]})
```

---

## 🔧 Agent Responsibilities

### **1. Health Agent** (`health_agent.py`)
**Status:** ✅ Fully functional  
**Tools:** `check_node_health`, `check_cluster_health`

**Use for:**
- Node health checks (taints, conditions, readiness)
- Cluster-wide node status overview
- Detecting unhealthy nodes

**Example Questions:**
- "Are all nodes healthy?"
- "What taints are on the master node?"
- "Check cluster node status"

---

### **2. Security Agent** (`security_agent.py`)
**Status:** ⚠️ Placeholder (no tools implemented)  
**Tools:** None currently

**Planned for:**
- RBAC permission checks
- Network policy monitoring
- Secret management (without exposing values)
- Security compliance audits

**Current Behavior:**
- Acknowledges security questions
- Explains tool limitations
- Suggests what security checks would be performed
- Routes to alternative agents if possible

---

### **3. Resources Agent** (`resources_agent.py`)
**Status:** ⚠️ Placeholder (no tools implemented)  
**Tools:** None currently

**Planned for:**
- Pod resource usage (CPU, memory via `kubectl top pods`)
- Node resource usage (CPU%, memory% via `kubectl top nodes`)
- Resource quotas and limits
- Capacity planning

**Current Behavior:**
- Acknowledges resource monitoring questions
- Explains that `kubectl top` tools need implementation
- Routes to `describe_get_expert` for resource specs

---

### **4. Monitor Agent** (`monitor_agent.py`)
**Status:** ✅ Partially functional  
**Tools:** `get_pod_logs` (more tools planned)

**Use for:**
- Retrieving pod logs (supports partial names)
- Troubleshooting pod failures
- Analyzing errors in logs

**Planned Tools:**
- `get_pod_events` - Recent events (restarts, errors)
- `get_cluster_events` - Cluster-wide events

**Example Questions:**
- "Show logs for nginx pod"
- "Why is the pod crashing?"
- "Get logs from coredns in kube-system"

---

### **5. Describe-Get Agent** (`describe_get_agent.py`)
**Status:** ✅ Fully functional  
**Tools:** `get_cluster_resources`, `describe_resource`

**Use for:**
- Listing any K8s resource (pods, services, deployments, etc.)
- Describing specific resources with details
- Counting resources (e.g., pods per namespace)
- Filtering and analyzing resource metadata

**Example Questions:**
- "List all pods"
- "How many pods are in each namespace?"
- "Describe the nginx service"
- "Show running pods in default namespace"

---

## 🎯 How the Supervisor Routes Questions

The supervisor analyzes user questions and routes to the appropriate agent:

| Question Pattern | Routes To | Example |
|-----------------|-----------|---------|
| Node health, taints, readiness | **Health Agent** | "Are nodes healthy?" |
| RBAC, policies, secrets | **Security Agent** | "Check RBAC permissions" (limited) |
| CPU/memory usage | **Resources Agent** | "Show CPU usage" (limited) |
| Pod logs, events, errors | **Monitor Agent** | "Show nginx logs" |
| List/describe resources | **Describe-Get Agent** | "List all pods" |

**Complex Questions (Sequential Routing):**
- "Show unhealthy pods and their logs"
  1. Describe-Get Agent → Find unhealthy pods
  2. Monitor Agent → Get logs for those pods
  3. Supervisor → Synthesize final answer

---

## 🔍 Example Workflows

### **Single-Agent Workflow**

```
User: "What taints are on the master node?"
  ↓
Supervisor: "This is a health question" → routes to health_expert
  ↓
Health Agent: Calls check_node_health("k8s-master-001")
  ↓
Health Agent: Returns node details with taints
  ↓
Supervisor: Synthesizes answer → "Master node has no taints"
```

### **Multi-Agent Workflow**

```
User: "Show failing pods and their logs"
  ↓
Supervisor: "Need to list pods first" → routes to describe_get_expert
  ↓
Describe-Get Agent: Calls get_cluster_resources("pods")
Describe-Get Agent: Filters for status != Running
Describe-Get Agent: Returns ["nginx-abc", "redis-xyz"]
  ↓
Supervisor: "Now get logs" → routes to monitor_expert
  ↓
Monitor Agent: Calls get_pod_logs("nginx-abc")
Monitor Agent: Calls get_pod_logs("redis-xyz")
Monitor Agent: Returns error logs
  ↓
Supervisor: Synthesizes → "Found 2 failing pods:\n1. nginx-abc: Error XYZ\n2. redis-xyz: Error ABC"
```

---

## 📝 Adding New Tools

To add new tools (e.g., resource monitoring):

### **Step 1: Create Tool in `utils/langchain_tools.py`**

```python
@tool
def get_pod_resource_usage(namespace: Optional[str] = None) -> str:
    """Get CPU and memory usage for pods using kubectl top."""
    if namespace:
        result = execute_kubectl_command(f"top pods -n {namespace}")
    else:
        result = execute_kubectl_command("top pods --all-namespaces")
    return json.dumps(result)
```

### **Step 2: Add to Tool Collection in `agents/tools.py`**

```python
from utils.langchain_tools import get_pod_resource_usage

RESOURCES_TOOLS = [
    get_pod_resource_usage  # Add new tool here
]
```

### **Step 3: Update Agent Prompt in `agents/resources_agent.py`**

Update the agent's prompt to mention the new tool:
```python
prompt="""...
- Use get_pod_resource_usage() for pod-level CPU/memory metrics
..."""
```

**That's it!** The agent will automatically use the new tool.

---

## ⚠️ Important Notes

1. **Sequential Execution:** Agents call tools ONE AT A TIME to prevent parallel function calling errors
2. **Tool Limitations:** Security and Resources agents have placeholder tools currently
3. **Transfer Mechanism:** Supervisor automatically creates `transfer_to_X_expert()` functions
4. **Dependencies:** Requires `langgraph-supervisor` and `langgraph` packages (install via `pip install langgraph-supervisor langgraph`)

---

## 🔄 Migration from Single Agent

If you're currently using `utils/langchain_agent.py` (single agent), here's how to migrate:

**Old (Single Agent):**
```python
from utils.langchain_agent import create_k8s_agent
from utils.langchain_tools import ALL_TOOLS

agent = create_k8s_agent(tools=ALL_TOOLS, api_key=api_key)
result = agent.answer_question("Check cluster health")
```

**New (Multi-Agent):**
```python
from agents import create_k8s_multiagent_system

app = create_k8s_multiagent_system(llm_model)
result = app.invoke({"messages": [{"role": "user", "content": "Check cluster health"}]})
final_answer = result["messages"][-1].content
```

---

## 🎓 Learning Resources

- **Sample Implementation:** See `sample/multiagent_sample.py` for the original multi-agent pattern
- **LangGraph Docs:** https://langchain-ai.github.io/langgraph/
- **Architecture Guide:** Read the markdown documentation at top of `sample/multiagent_sample.py`

---

## 📦 Dependencies

```bash
pip install langgraph-supervisor  # Pre-built supervisor pattern
pip install langgraph            # Graph-based workflow engine
pip install langchain            # Core framework
pip install langchain-google-genai  # For Gemini models
```

---

## ✅ Testing

Test the multi-agent system:

```python
from langchain_google_genai import ChatGoogleGenerativeAI
from agents import create_k8s_multiagent_system

llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-exp", temperature=0.2)
app = create_k8s_multiagent_system(llm, verbose=True)

# Test questions
questions = [
    "Are all nodes healthy?",           # → Health Agent
    "List all pods",                     # → Describe-Get Agent
    "Show logs for nginx pod",           # → Monitor Agent
    "How many pods per namespace?",      # → Describe-Get Agent
    "Check master node taints"           # → Health Agent
]

for q in questions:
    print(f"\n{'='*60}\nQ: {q}\n{'='*60}")
    result = app.invoke({"messages": [{"role": "user", "content": q}]})
    print(result["messages"][-1].content)
```

---

## 🚀 Next Steps

1. **Implement Resource Monitoring Tools:** Add `get_pod_resource_usage` and `get_node_resource_usage` in `utils/langchain_tools.py`
2. **Implement Security Tools:** Add RBAC, network policy, and secret checking tools
3. **Add Event Monitoring:** Implement `get_pod_events` and `get_cluster_events`
4. **Integrate with Dashboard:** Update `app/dashboard.py` to use multi-agent system
5. **Performance Testing:** Test with complex multi-step questions

---

**Built with ❤️ following the supervisor pattern from `sample/multiagent_sample.py`**
