# 🤖 LangChain Agent Architecture & Flow

## 📊 Complete System Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                   USER                                      │
│                  Types: "Show all pods in the cluster"                      │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        STREAMLIT UI (dashboard.py)                          │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │  if prompt := st.chat_input("Ask me about YOUR cluster..."):      │    │
│  │      st.session_state.chat_history.append({"role": "user", ...})  │    │
│  │      cluster_context = build_cluster_context()                    │    │
│  │      result = st.session_state.k8s_agent.answer_question(         │    │
│  │          question=prompt,                                          │    │
│  │          cluster_context=cluster_context                           │    │
│  │      )                                                              │    │
│  │      ai_response = result.get("answer")                            │    │
│  │      st.session_state.chat_history.append({"role": "assistant"})  │    │
│  └────────────────────────────────────────────────────────────────────┘    │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│              LANGCHAIN AGENT (utils/langchain_agent.py)                     │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │  class LangChainK8sAgent:                                          │    │
│  │      def answer_question(self, question, cluster_context=""):     │    │
│  │          # Enhance question with context                           │    │
│  │          enhanced_question = f"Context: {cluster_context}          │    │
│  │                                Question: {question}"                │    │
│  │                                                                     │    │
│  │          # ONE LINE - LangChain magic!                             │    │
│  │          result = self.executor.invoke({"input": enhanced_q})     │    │
│  │                                                                     │    │
│  │          return {                                                  │    │
│  │              "answer": result.get("output"),                       │    │
│  │              "success": True                                       │    │
│  │          }                                                          │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  Components:                                                                │
│  • ChatGoogleGenerativeAI(model="gemini-2.0-flash-exp")                   │
│  • AgentExecutor (orchestrates everything)                                 │
│  • ConversationBufferMemory (auto conversation tracking)                   │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                  LANGCHAIN FRAMEWORK (Internal Magic)                       │
│                                                                             │
│  Step 1: Send to Gemini AI with tools schema                               │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │  POST https://generativelanguage.googleapis.com/v1beta/...        │    │
│  │  {                                                                 │    │
│  │    "contents": [{                                                  │    │
│  │      "parts": [{"text": "Show all pods in the cluster"}]          │    │
│  │    }],                                                             │    │
│  │    "tools": [{                                                     │    │
│  │      "function_declarations": [                                    │    │
│  │        {                                                           │    │
│  │          "name": "get_cluster_resources",                          │    │
│  │          "description": "List Kubernetes resources...",            │    │
│  │          "parameters": {                                           │    │
│  │            "type": "object",                                       │    │
│  │            "properties": {                                         │    │
│  │              "resource_type": {"type": "string"},                  │    │
│  │              "namespace": {"type": "string"}                       │    │
│  │            }                                                        │    │
│  │          }                                                          │    │
│  │        },                                                           │    │
│  │        { /* 4 more tools... */ }                                   │    │
│  │      ]                                                              │    │
│  │    }]                                                               │    │
│  │  }                                                                  │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  Step 2: Gemini AI responds with function call                             │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │  {                                                                 │    │
│  │    "candidates": [{                                                │    │
│  │      "content": {                                                  │    │
│  │        "parts": [{                                                 │    │
│  │          "functionCall": {                                         │    │
│  │            "name": "get_cluster_resources",                        │    │
│  │            "args": {                                               │    │
│  │              "resource_type": "pods"                               │    │
│  │            }                                                        │    │
│  │          }                                                          │    │
│  │        }]                                                           │    │
│  │      }                                                              │    │
│  │    }]                                                               │    │
│  │  }                                                                  │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  Step 3: LangChain executes the tool automatically                         │
│          ↓                                                                  │
└──────────┼──────────────────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      TOOLS (utils/langchain_tools.py)                       │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │  @tool                                                             │    │
│  │  def get_cluster_resources(resource_type: str,                    │    │
│  │                            namespace: Optional[str] = None) -> str:│    │
│  │      """List Kubernetes resources like pods, nodes, services."""  │    │
│  │                                                                     │    │
│  │      if namespace:                                                 │    │
│  │          result = execute_kubectl_command(                         │    │
│  │              f"get {resource_type} -n {namespace} -o json"         │    │
│  │          )                                                          │    │
│  │      else:                                                          │    │
│  │          result = execute_kubectl_command(                         │    │
│  │              f"get {resource_type} --all-namespaces -o json"       │    │
│  │          )                                                          │    │
│  │                                                                     │    │
│  │      return json.dumps(result)                                     │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  Available Tools (5 total):                                                │
│  1. get_cluster_resources  → kubectl get                                   │
│  2. describe_resource      → kubectl describe                              │
│  3. get_pod_logs           → kubectl logs                                  │
│  4. check_node_health      → kubectl describe node                         │
│  5. check_cluster_health   → kubectl get nodes -o wide                     │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    KUBECTL COMMAND EXECUTION                                │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │  def execute_kubectl_command(command, node="k8s-master-001",      │    │
│  │                               zone="us-central1-a", timeout=20):   │    │
│  │                                                                     │    │
│  │      full_command = (                                              │    │
│  │          "export KUBECONFIG=/etc/kubernetes/admin.conf && "        │    │
│  │          f"kubectl {command}"                                      │    │
│  │      )                                                              │    │
│  │                                                                     │    │
│  │      ssh_command = [                                               │    │
│  │          "gcloud", "compute", "ssh", node,                         │    │
│  │          f"--zone={zone}",                                         │    │
│  │          f"--command={full_command}"                               │    │
│  │      ]                                                              │    │
│  │                                                                     │    │
│  │      result = subprocess.run(ssh_command, ...)                     │    │
│  │                                                                     │    │
│  │      return {'success': True, 'output': result.stdout}             │    │
│  └────────────────────────────────────────────────────────────────────┘    │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          GOOGLE CLOUD PLATFORM                              │
│  ┌───────────────────────────────────────────────────────────────────┐     │
│  │  gcloud compute ssh k8s-master-001 --zone=us-central1-a           │     │
│  │  --command="kubectl get pods --all-namespaces -o json"            │     │
│  └───────────────────────────────────────────────────────────────────┘     │
│                                 │                                           │
│                                 ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────┐       │
│  │              KUBERNETES CLUSTER (k8s-master-001)                │       │
│  │  ┌────────────────────────────────────────────────────────┐     │       │
│  │  │  $ kubectl get pods --all-namespaces -o json           │     │       │
│  │  │                                                         │     │       │
│  │  │  {                                                      │     │       │
│  │  │    "apiVersion": "v1",                                 │     │       │
│  │  │    "items": [                                          │     │       │
│  │  │      {                                                  │     │       │
│  │  │        "metadata": {                                   │     │       │
│  │  │          "name": "coredns-7c5566588d-abc123",          │     │       │
│  │  │          "namespace": "kube-system"                    │     │       │
│  │  │        },                                               │     │       │
│  │  │        "status": {"phase": "Running"}                  │     │       │
│  │  │      },                                                 │     │       │
│  │  │      { /* more pods... */ }                            │     │       │
│  │  │    ]                                                    │     │       │
│  │  │  }                                                      │     │       │
│  │  └────────────────────────────────────────────────────────┘     │       │
│  └─────────────────────────────────────────────────────────────────┘       │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │ JSON output
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    RETURN PATH (Bottom to Top)                              │
│                                                                             │
│  Kubernetes → GCloud SSH → execute_kubectl_command() → Tool Function       │
│       ↓                                                                     │
│  Tool returns: '{"success": true, "output": "{...JSON data...}"}'          │
│       ↓                                                                     │
│  LangChain receives tool result                                            │
│       ↓                                                                     │
│  Step 4: LangChain sends result back to Gemini AI                          │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │  POST https://generativelanguage.googleapis.com/v1beta/...        │    │
│  │  {                                                                 │    │
│  │    "contents": [{                                                  │    │
│  │      "parts": [{                                                   │    │
│  │        "functionResponse": {                                       │    │
│  │          "name": "get_cluster_resources",                          │    │
│  │          "response": {                                             │    │
│  │            "content": "{...pod data...}"                           │    │
│  │          }                                                          │    │
│  │        }                                                            │    │
│  │      }]                                                             │    │
│  │    }]                                                               │    │
│  │  }                                                                  │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│       ↓                                                                     │
│  Step 5: Gemini AI synthesizes final answer                                │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │  {                                                                 │    │
│  │    "candidates": [{                                                │    │
│  │      "content": {                                                  │    │
│  │        "parts": [{                                                 │    │
│  │          "text": "I found 12 pods running in your cluster:\n      │    │
│  │                   \n1. coredns-7c5566588d-abc123 (kube-system)    │    │
│  │                   \n2. kube-proxy-xyz789 (kube-system)            │    │
│  │                   \n... (10 more pods)"                            │    │
│  │        }]                                                           │    │
│  │      }                                                              │    │
│  │    }]                                                               │    │
│  │  }                                                                  │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│       ↓                                                                     │
│  LangChain extracts answer → Returns to agent                              │
│       ↓                                                                     │
│  Agent returns {"answer": "I found 12 pods...", "success": true}           │
│       ↓                                                                     │
│  Streamlit displays answer to user                                         │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                                   USER                                      │
│            Sees: "I found 12 pods running in your cluster:                 │
│                   1. coredns-7c5566588d-abc123 (kube-system)               │
│                   2. kube-proxy-xyz789 (kube-system)                       │
│                   ... (10 more pods)"                                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Detailed Step-by-Step Flow

### **Phase 1: User Input**
```python
# File: app/dashboard.py (line ~2000)

if prompt := st.chat_input("Ask me about YOUR cluster..."):
    # Step 1: Save user message
    st.session_state.chat_history.append({
        "role": "user", 
        "content": prompt
    })
    
    # Step 2: Build context from cached VM/Pod data
    cluster_context = build_cluster_context()
    # Returns: "2 VMs (master, worker), 12 pods, 10 Running..."
```

---

### **Phase 2: LangChain Agent Processing**
```python
# File: utils/langchain_agent.py (line ~100)

class LangChainK8sAgent:
    def answer_question(self, question, cluster_context=""):
        # Step 3: Enhance question with context
        if cluster_context:
            enhanced_question = f"""
            Context about current cluster state:
            {cluster_context[:500]}
            
            User question: {question}
            """
        
        # Step 4: ONE INVOKE - LangChain handles everything!
        result = self.executor.invoke({"input": enhanced_question})
        #   ↑
        #   This single line does:
        #   - Sends question + tools to Gemini
        #   - Gemini decides which tool(s) to call
        #   - Executes tool functions automatically
        #   - Sends results back to Gemini
        #   - Gets final answer from Gemini
        #   - Saves to conversation memory
        
        # Step 5: Return formatted response
        return {
            "answer": result.get("output"),
            "intermediate_steps": result.get("intermediate_steps"),
            "success": True
        }
```

---

### **Phase 3: LangChain Internal Magic**
```python
# This happens INSIDE self.executor.invoke() automatically:

# 3.1: Build function schema for Gemini
tools_schema = [
    {
        "name": "get_cluster_resources",
        "description": "List Kubernetes resources like pods, nodes...",
        "parameters": {
            "type": "object",
            "properties": {
                "resource_type": {"type": "string"},
                "namespace": {"type": "string", "optional": True}
            }
        }
    },
    # ... 4 more tools
]

# 3.2: Send to Gemini with function calling enabled
gemini_request = {
    "contents": [{"parts": [{"text": enhanced_question}]}],
    "tools": [{"function_declarations": tools_schema}]
}

# 3.3: Gemini responds with function call
gemini_response = {
    "functionCall": {
        "name": "get_cluster_resources",
        "args": {"resource_type": "pods"}
    }
}

# 3.4: LangChain executes the function
tool_result = get_cluster_resources(resource_type="pods")

# 3.5: Send result back to Gemini
gemini_final_request = {
    "contents": [{
        "parts": [{
            "functionResponse": {
                "name": "get_cluster_resources",
                "response": {"content": tool_result}
            }
        }]
    }]
}

# 3.6: Gemini creates final answer
final_answer = "I found 12 pods running in your cluster..."
```

---

### **Phase 4: Tool Execution**
```python
# File: utils/langchain_tools.py (line ~60)

@tool
def get_cluster_resources(resource_type: str, namespace: Optional[str] = None) -> str:
    """List Kubernetes resources like pods, nodes, services."""
    
    # Step 6: Build kubectl command
    if namespace:
        cmd = f"get {resource_type} -n {namespace} -o json"
    else:
        cmd = f"get {resource_type} --all-namespaces -o json"
    
    # Step 7: Execute via SSH
    result = execute_kubectl_command(cmd)
    
    # Returns: {'success': True, 'output': '{...JSON...}'}
    return json.dumps(result)


# File: utils/langchain_tools.py (line ~10)

def execute_kubectl_command(command, node="k8s-master-001", zone="us-central1-a"):
    # Step 8: Build SSH command
    full_command = f"export KUBECONFIG=/etc/kubernetes/admin.conf && kubectl {command}"
    
    ssh_command = [
        "gcloud", "compute", "ssh", node,
        f"--zone={zone}",
        f"--command={full_command}"
    ]
    
    # Step 9: Execute via subprocess
    result = subprocess.run(ssh_command, capture_output=True, text=True)
    
    # Step 10: Return result
    if result.returncode == 0:
        return {'success': True, 'output': result.stdout}
    else:
        return {'success': False, 'error': result.stderr}
```

---

### **Phase 5: Display Response**
```python
# File: app/dashboard.py (line ~2010)

# Step 11: Extract answer from result
result = st.session_state.k8s_agent.answer_question(
    question=prompt,
    cluster_context=cluster_context
)

ai_response = result.get("answer")

# Step 12: Save to chat history
st.session_state.chat_history.append({
    "role": "assistant",
    "content": ai_response
})

# Step 13: Display to user
with st.chat_message("assistant", avatar=k8s_avatar):
    st.markdown(ai_response)
```

---

## 📦 Key Components Summary

| Component | File | Purpose | Key Code |
|-----------|------|---------|----------|
| **UI Layer** | `app/dashboard.py` | User interaction | `st.chat_input()`, `st.chat_message()` |
| **Agent** | `utils/langchain_agent.py` | Orchestration | `self.executor.invoke()` |
| **Tools** | `utils/langchain_tools.py` | Kubernetes operations | `@tool` decorated functions |
| **Execution** | `utils/langchain_tools.py` | SSH + kubectl | `subprocess.run()` with gcloud |
| **AI Model** | LangChain + Google | Decision making | `ChatGoogleGenerativeAI` |
| **Memory** | LangChain built-in | Conversation history | `ConversationBufferMemory` |

---

## 🎯 The Magic: Compare Before vs After

### **Custom Agent (Before):**
```
User → Dashboard → Agent (manual 3 phases) → Tools → K8s
                     ↓
                 Phase 1: Planning prompt
                 Phase 2: Manual tool exec
                 Phase 3: Synthesis prompt
```

### **LangChain Agent (After):**
```
User → Dashboard → Agent.executor.invoke() → [LangChain Magic] → Tools → K8s
                            ↑
                    Single call does everything!
```

**That's the beauty of LangChain!** 🚀
