# K8s AI Assistant - Complete Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                           USER INTERACTION LAYER                                    │
│  • Web Browser (http://localhost:7000 or http://<WSL_IP>:7000 from Windows)        │
│  • Sends natural language questions about Kubernetes cluster                        │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         │ HTTP POST/GET
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                         FLASK WEB APP                                               │
│  • Host: 0.0.0.0                                                                    │
│  • Port: 7000                                                                       │
│  • File: app2.0/app.py                                                              │
│  • Functions:                                                                       │
│    - /ask endpoint: Receives user questions                                         │
│    - Calls ask_k8s_agent(question)                                                  │
│    - Maintains global conversation state (_conversation_state)                      │
│  • Virtual Environment: app2.0/.venv                                                │
│  • Management: app2.0/startup.sh (start/stop/restart/status/logs)                   │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         │ Python function call
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                      SUPERVISOR AGENT (k8s_agent.py)                                │
│  • Framework: LangGraph Workflow                                                    │
│  • LLM: Claude Haiku (Anthropic)                                                    │
│  • Temperature: 0 (deterministic)                                                   │
│                                                                                     │
│  ROUTING PROCESS (4 Steps):                                                         │
│  ┌───────────────────────────────────────────────────────────────────────────┐    │
│  │ STEP 1: Question Type Classification                                      │    │
│  │  • K8S: Kubernetes questions                                              │    │
│  │  • GREETING: "hi", "hello", "hey"                                         │    │
│  │  • META: "last N questions", "conversation history"                       │    │
│  │  • CASUAL: General conversation (redirect to K8s topics)                  │    │
│  └───────────────────────────────────────────────────────────────────────────┘    │
│                              ▼                                                      │
│  ┌───────────────────────────────────────────────────────────────────────────┐    │
│  │ STEP 2: Category Classification (if K8S)                                  │    │
│  │  • HEALTH: "restarted", "node status", "events", "taints"                 │    │
│  │  • DESCRIBE: "list", "show", "get", "pods on node", "logs", "taints"     │    │
│  │  • RESOURCES: "cpu usage", "memory usage", "top nodes/pods"               │    │
│  │  • MONITOR: "prometheus metrics", "trends", "last X minutes"              │    │
│  │  • OPERATIONS: "scale", "restart", "delete", "create", "apply"            │    │
│  └───────────────────────────────────────────────────────────────────────────┘    │
│                              ▼                                                      │
│  ┌───────────────────────────────────────────────────────────────────────────┐    │
│  │ STEP 3: Sub-Question Extraction                                           │    │
│  │  • Parses complex questions into agent-specific sub-queries               │    │
│  │  • Example: "show node health and pod logs" →                             │    │
│  │    HEALTH: "show node health"                                             │    │
│  │    DESCRIBE: "show pod logs"                                              │    │
│  └───────────────────────────────────────────────────────────────────────────┘    │
│                              ▼                                                      │
│  ┌───────────────────────────────────────────────────────────────────────────┐    │
│  │ STEP 4: Parallel Agent Execution                                          │    │
│  │  • Routes to 1 or more specialized agents                                 │    │
│  │  • Agents execute in parallel when possible                               │    │
│  │  • Aggregates responses and returns to Flask                              │    │
│  └───────────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────────────┘
           │              │              │              │              │
           ▼              ▼              ▼              ▼              ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│   HEALTH     │ │   DESCRIBE   │ │  RESOURCES   │ │   MONITOR    │ │ OPERATIONS   │
│    AGENT     │ │    AGENT     │ │    AGENT     │ │    AGENT     │ │    AGENT     │
│              │ │              │ │              │ │              │ │              │
│ Port: 8000   │ │ Port: 8002   │ │ Port: 8001   │ │ Port: 8004   │ │ Port: 8003   │
│ URL:         │ │ URL:         │ │ URL:         │ │ URL:         │ │ URL:         │
│ http://      │ │ http://      │ │ http://      │ │ http://      │ │ http://      │
│ 127.0.0.1:   │ │ 127.0.0.1:   │ │ 127.0.0.1:   │ │ 127.0.0.1:   │ │ 127.0.0.1:   │
│ 8000/mcp     │ │ 8002/mcp     │ │ 8001/mcp     │ │ 8004/mcp     │ │ 8003/mcp     │
│              │ │              │ │              │ │              │ │              │
│ Purpose:     │ │ Purpose:     │ │ Purpose:     │ │ Purpose:     │ │ Purpose:     │
│ • Node       │ │ • Resource   │ │ • Current    │ │ • Prometheus │ │ • Cluster    │
│   health     │ │   discovery  │ │   resource   │ │   metrics    │ │   changes    │
│ • Cluster    │ │ • Listing    │ │   snapshots  │ │ • Time-      │ │ • Scaling    │
│   events     │ │ • Details    │ │ • kubectl    │ │   series     │ │ • Restarts   │
│ • Node       │ │ • Pod logs   │ │   top        │ │   queries    │ │ • Create/    │
│   conditions │ │ • YAML       │ │ • Node/Pod   │ │ • Trend      │ │   Delete     │
│ • Taints     │ │   export     │ │   usage      │ │   analysis   │ │ • Apply      │
│              │ │ • Taints     │ │              │ │              │ │   YAML       │
└──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘
       │                 │                 │                 │                 │
       │                 │                 │                 │                 │
       └─────────────────┴─────────────────┴─────────────────┴─────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                         MCP SERVERS (FastMCP)                                       │
│  • Framework: Model Context Protocol (FastMCP)                                      │
│  • Cache: 60-second TTL (except Operations and Monitor)                             │
│  • Virtual Environment: app2.0/.venv                                                │
│  • Management: app2.0/startup.sh                                                    │
│                                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────────┐  │
│  │ MCP HEALTH SERVER (http://127.0.0.1:8000/mcp)                               │  │
│  │ • File: app2.0/MCP/mcp_health/mcp_health_server.py                          │  │
│  │ • Port: 8000                                                                 │  │
│  │ • Tools:                                                                     │  │
│  │   1. get_cluster_nodes() - List all nodes                                   │  │
│  │   2. describe_node(node_name) - Node health with taints + lastTransitionTime│  │
│  │   3. get_cluster_events(namespace) - Recent cluster events                  │  │
│  └─────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────────┐  │
│  │ MCP DESCRIBE SERVER (http://127.0.0.1:8002/mcp)                             │  │
│  │ • File: app2.0/MCP/mcp_describe/mcp_describe_server.py                      │  │
│  │ • Port: 8002                                                                 │  │
│  │ • Tools:                                                                     │  │
│  │   1. list_k8s_resources(resource_type, namespace) - List resources          │  │
│  │   2. describe_k8s_resource(resource_type, name, namespace) - Details        │  │
│  │   3. count_k8s_resources(resource_type, namespace) - Count resources        │  │
│  │   4. get_all_resources_in_namespace(namespace) - All resources in NS        │  │
│  │   5. get_resource_yaml(resource_type, name, namespace) - Export YAML        │  │
│  │   6. get_pod_logs(pod_name, namespace, container, tail, previous) - Logs    │  │
│  └─────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────────┐  │
│  │ MCP RESOURCES SERVER (http://127.0.0.1:8001/mcp)                            │  │
│  │ • File: app2.0/MCP/mcp_resources/mcp_resources_server.py                    │  │
│  │ • Port: 8001                                                                 │  │
│  │ • Tools:                                                                     │  │
│  │   1. get_node_resources() - kubectl top nodes                               │  │
│  │   2. get_pod_resources(namespace, pod) - kubectl top pods                   │  │
│  │   3. get_node_allocations(node_name) - Resource requests vs capacity        │  │
│  └─────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────────┐  │
│  │ MCP MONITOR SERVER (http://127.0.0.1:8004/mcp)                              │  │
│  │ • File: app2.0/MCP/mcp_monitor/mcp_monitor_server.py                        │  │
│  │ • Port: 8004                                                                 │  │
│  │ • Tools:                                                                     │  │
│  │   1. query_prometheus(query, time_range) - PromQL queries                   │  │
│  │   2. get_node_metrics(node_name, metric_type, time_range) - Node metrics    │  │
│  │   3. get_pod_metrics(pod_name, namespace, metric, time_range) - Pod metrics │  │
│  │   4. compare_metrics(query1, query2, time_range) - Metric comparison        │  │
│  │   5. get_metric_trend(query, time_range) - Analyze trends                   │  │
│  └─────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────────┐  │
│  │ MCP OPERATIONS SERVER (http://127.0.0.1:8003/mcp)                           │  │
│  │ • File: app2.0/MCP/mcp_operations/mcp_operations_server.py                  │  │
│  │ • Port: 8003                                                                 │  │
│  │ • Tools:                                                                     │  │
│  │   1. scale_deployment(name, namespace, replicas) - Scale deployments        │  │
│  │   2. restart_deployment(name, namespace) - Restart pods                     │  │
│  │   3. delete_resource(resource_type, name, namespace) - Delete resources     │  │
│  │   4. create_resource_from_yaml(yaml_content) - Create from YAML            │  │
│  │   5. apply_yaml(yaml_content) - kubectl apply                               │  │
│  └─────────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         │ SSH via gcloud compute ssh
                                         │ Command: gcloud compute ssh swinvm15@k8s-master-001 \
                                         │          --zone=us-central1-a \
                                         │          --project=beaming-age-463822-k7 \
                                         │          --command="kubectl ..."
                                         │ Key: ~/.ssh/google_compute_engine
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                   GOOGLE CLOUD PLATFORM (GCP)                                       │
│  • Project: beaming-age-463822-k7                                                   │
│  • Region: us-central1                                                              │
│  • Zone: us-central1-a                                                              │
│                                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────────┐  │
│  │ K8S-MASTER-001 (Control Plane)                                              │  │
│  │ • VM Type: e2-medium (2 vCPU, 4GB RAM)                                      │  │
│  │ • Internal IP: 10.128.0.2                                                   │  │
│  │ • External IP: [Dynamic - check with gcloud compute instances list]        │  │
│  │ • FQDN: k8s-master-001.us-central1-a.c.beaming-age-463822-k7.internal      │  │
│  │ • SSH User: swinvm15                                                        │  │
│  │ • SSH Command: gcloud compute ssh swinvm15@k8s-master-001 \                │  │
│  │                --zone=us-central1-a --project=beaming-age-463822-k7         │  │
│  │ • Roles:                                                                    │  │
│  │   - Kubernetes API Server                                                   │  │
│  │   - etcd                                                                    │  │
│  │   - kubectl execution point (all MCP servers connect here)                 │  │
│  │   - CoreDNS pods                                                            │  │
│  │ • Taints: <none>                                                            │  │
│  └─────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────────┐  │
│  │ K8S-WORKER-01 (Worker Node)                                                 │  │
│  │ • VM Type: e2-medium (2 vCPU, 4GB RAM)                                      │  │
│  │ • Internal IP: 10.128.0.3                                                   │  │
│  │ • External IP: [Dynamic - check with gcloud compute instances list]        │  │
│  │ • Roles:                                                                    │  │
│  │   - Runs application workloads                                              │  │
│  │   - kube-proxy pod                                                          │  │
│  │   - kube-flannel pod (CNI)                                                  │  │
│  │ • Taints: node.kubernetes.io/unschedulable:NoSchedule                       │  │
│  │ • Last Restart: 2025-09-14T06:17:36Z                                        │  │
│  └─────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────────┐  │
│  │ PROMETHEUS SERVER (External to K8s)                                         │  │
│  │ • URL: http://34.59.188.124:9090                                            │  │
│  │ • Public IP: 34.59.188.124                                                  │  │
│  │ • Port: 9090                                                                │  │
│  │ • Purpose: Metrics collection and querying                                  │  │
│  │ • Accessed by: Monitor Agent (MCP Monitor Server)                           │  │
│  │ • Metrics: Node CPU/Memory, Pod CPU/Memory, API server, etcd                │  │
│  └─────────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         │ Kubernetes API calls
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                       KUBERNETES API SERVER                                         │
│  • Running on: k8s-master-001                                                       │
│  • Port: 6443 (HTTPS)                                                               │
│  • Auth: kubeconfig on master node                                                  │
│  • All kubectl commands are executed through SSH → kubectl → K8s API               │
└─────────────────────────────────────────────────────────────────────────────────────┘


═══════════════════════════════════════════════════════════════════════════════════════
                             DATA FLOW EXAMPLE
═══════════════════════════════════════════════════════════════════════════════════════

User Question: "What pods are running on the worker node?"

1. Browser → http://localhost:7000/ask
   POST {"question": "What pods are running on the worker node?"}

2. Flask (0.0.0.0:7000) → ask_k8s_agent("What pods are running on the worker node?")

3. Supervisor Agent:
   - STEP 1: Classify → K8S
   - STEP 2: Category → DESCRIBE (list/show queries)
   - STEP 3: Extract → DESCRIBE: "list pods on k8s-worker-01"
   - STEP 4: Route → Describe Agent

4. Describe Agent → http://127.0.0.1:8002/mcp
   - Calls list_k8s_resources tool

5. MCP Describe Server (127.0.0.1:8002):
   - Executes: gcloud compute ssh swinvm15@k8s-master-001 \
               --zone=us-central1-a \
               --project=beaming-age-463822-k7 \
               --command="kubectl get pods --all-namespaces \
                          --field-selector spec.nodeName=k8s-worker-01"

6. k8s-master-001 (10.128.0.2):
   - Executes: kubectl → K8s API (localhost:6443)
   - Returns: 2 pods (kube-flannel-ds-sc4pz, kube-proxy-9rsbd)

7. Response bubbles back:
   MCP Server → Describe Agent → Supervisor → Flask → Browser

8. User sees: "2 pods running on k8s-worker-01:
              • kube-flannel-ds-sc4pz (kube-flannel namespace)
              • kube-proxy-9rsbd (kube-system namespace)"


═══════════════════════════════════════════════════════════════════════════════════════
                            KEY TECHNOLOGIES
═══════════════════════════════════════════════════════════════════════════════════════

• Frontend: Web Browser (HTTP client)
• Backend: Flask (Python web framework) - Port 7000, Host 0.0.0.0
• Agent Framework: LangGraph (workflow orchestration)
• LLM: Claude Haiku via Anthropic API (temperature=0, max_tokens=1024)
• MCP Framework: FastMCP (Model Context Protocol servers)
• Cloud Platform: Google Cloud Platform (GCP)
  - Project: beaming-age-463822-k7
  - Zone: us-central1-a
• Container Orchestration: Kubernetes (v1.28+)
• Metrics: Prometheus - http://34.59.188.124:9090
• Networking: 
  - SSH via gcloud compute ssh
  - Key: ~/.ssh/google_compute_engine
  - User: swinvm15
• Monitoring: Prometheus Node Exporter, kube-state-metrics
• JSON Processing: jq (on k8s-master-001)
• Virtual Environment: Python venv (.venv in app2.0/)
• Process Management: startup.sh (start/stop/restart/status/logs)


═══════════════════════════════════════════════════════════════════════════════════════
                          PORT ASSIGNMENTS SUMMARY
═══════════════════════════════════════════════════════════════════════════════════════

Local Services (127.0.0.1):
├── Flask Web App:              7000  (0.0.0.0:7000 - accessible externally)
├── MCP Health Server:          8000  (http://127.0.0.1:8000/mcp)
├── MCP Resources Server:       8001  (http://127.0.0.1:8001/mcp)
├── MCP Describe Server:        8002  (http://127.0.0.1:8002/mcp)
├── MCP Operations Server:      8003  (http://127.0.0.1:8003/mcp)
└── MCP Monitor Server:         8004  (http://127.0.0.1:8004/mcp)

GCP Services:
├── Prometheus:                 9090  (34.59.188.124:9090 - public IP)
└── Kubernetes API:             6443  (k8s-master-001:6443 - HTTPS)


═══════════════════════════════════════════════════════════════════════════════════════
                          IP ADDRESS SUMMARY
═══════════════════════════════════════════════════════════════════════════════════════

Local System:
├── Flask App Host:             0.0.0.0 (all interfaces)
├── Flask App Access:           localhost or 127.0.0.1 or <WSL_IP>
└── MCP Servers:                127.0.0.1 (localhost only)

GCP Internal IPs (Private Network):
├── k8s-master-001:             10.128.0.2
└── k8s-worker-01:              10.128.0.3

GCP External IPs (Public - Dynamic):
├── k8s-master-001:             [Check: gcloud compute instances list]
├── k8s-worker-01:              [Check: gcloud compute instances list]
└── Prometheus:                 34.59.188.124 (static/reserved)


═══════════════════════════════════════════════════════════════════════════════════════
                         CONVERSATION STATE
═══════════════════════════════════════════════════════════════════════════════════════

Global State Management:
• Variable: _conversation_state = {"messages": []}
• Scope: Maintained across ask_k8s_agent() calls
• Functions:
  - get_conversation_state() - Returns current state
  - reset_conversation() - Clears history
• Capabilities:
  - Handles greetings: "hi" → Welcome message
  - Handles meta queries: "what were my last 5 questions?" → Shows history
  - Handles K8s queries: Routes to specialized agents
```
