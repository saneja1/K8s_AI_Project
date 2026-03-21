"""
Architecture Diagram Page
Interactive visualization of the multi-agent system architecture
"""

import streamlit as st
import graphviz

st.set_page_config(page_title="System Architecture", layout="wide", page_icon="🏗️")

st.title("🏗️ K8s Multi-Agent System Architecture")
st.markdown("---")

# Introduction
st.markdown("""
This diagram shows how the **Supervisor Agent** routes queries to specialized agents, 
which communicate with **MCP Servers** to execute tools that interact with the **Kubernetes Cluster** and **Prometheus**.
""")

# Create tabs for different views
tab1, tab2, tab3 = st.tabs(["📊 Full Architecture", "🔍 Detailed Flow Examples", "📖 Component Glossary"])

with tab1:
    st.subheader("Complete System Architecture")
    
    st.info("💡 **Flow**: User Query → Supervisor analyzes & routes → Agent calls tool via MCP → Tool executes on K8s/Prometheus → Response flows back")
    
    # Create the main architecture diagram
    dot = graphviz.Digraph(comment='K8s Multi-Agent Architecture')
    dot.attr(rankdir='TB', splines='ortho', nodesep='1.0', ranksep='1.5', bgcolor='white')
    dot.attr('node', shape='box', style='rounded,filled', fontname='Arial', fontsize='12', margin='0.3')
    dot.attr('edge', fontname='Arial', fontsize='11', color='#666666')
    
    # User Layer
    with dot.subgraph(name='cluster_user') as c:
        c.attr(label='👤 USER INTERFACE', style='filled,rounded', color='#E3F2FD', fontsize='15', fontname='Arial Bold', labeljust='l')
        c.node('CLI', '🖥️ CLI\n(cli.py)\n\nCommand: python cli.py -q "query"', fillcolor='#BBDEFB', shape='box', width='3')
        c.node('WebUI', '🌐 Web UI\n(Flask app.py:7000)\n\nBrowser Interface', fillcolor='#BBDEFB', shape='box', width='3')
    
    # Supervisor Layer with routing logic
    with dot.subgraph(name='cluster_supervisor') as c:
        c.attr(label='🎯 SUPERVISOR (LangGraph + Claude Sonnet 4.5)', style='filled,rounded', color='#C8E6C9', fontsize='15', fontname='Arial Bold', labeljust='l')
        c.node('Supervisor', '''🎯 Supervisor Agent
        
Routing Logic:
• Analyzes query keywords
• Checks agent capabilities  
• Routes to best agent
• Can call multiple agents''', 
               fillcolor='#A5D6A7', shape='box', style='rounded,filled,bold', width='5')
    
    # Agent Layer
    with dot.subgraph(name='cluster_agents') as c:
        c.attr(label='🤖 SPECIALIZED AGENTS (Each has LangGraph workflow)', style='filled,rounded', color='#FFF9C4', fontsize='15', fontname='Arial Bold', labeljust='l')
        c.node('HealthAgent', '''❤️ Health Agent
        
Handles: health, status,
ready, liveness checks''', fillcolor='#FFF59D', width='2.5', height='1.2')
        c.node('DescribeAgent', '''📋 Describe Agent
        
Handles: describe, get,
show details, config''', fillcolor='#FFF59D', width='2.5', height='1.2')
        c.node('ResourcesAgent', '''📊 Resources Agent
        
Handles: capacity, limits,
quotas, allocations''', fillcolor='#FFF59D', width='2.5', height='1.2')
        c.node('OperationsAgent', '''⚙️ Operations Agent
        
Handles: create, delete,
scale, apply, patch''', fillcolor='#FFF59D', width='2.5', height='1.2')
        c.node('MonitorAgent', '''📈 Monitor Agent
        
Handles: metrics, CPU,
memory, Prometheus''', fillcolor='#FFF59D', width='2.5', height='1.2')
    
    # MCP Server Layer
    with dot.subgraph(name='cluster_mcp') as c:
        c.attr(label='🔌 MCP SERVERS (FastMCP - Model Context Protocol)', style='filled,rounded', color='#FFCDD2', fontsize='15', fontname='Arial Bold', labeljust='l')
        c.node('MCP_Health', '''🔌 Health MCP
:8000

Tools:
• check_pod_health
• check_readiness''', fillcolor='#EF9A9A', shape='component', width='2.5', height='1.2')
        c.node('MCP_Describe', '''🔌 Describe MCP
:8002

Tools:
• describe_resource
• get_yaml''', fillcolor='#EF9A9A', shape='component', width='2.5', height='1.2')
        c.node('MCP_Resources', '''🔌 Resources MCP
:8001

Tools:
• get_node_resources
• get_pod_resources''', fillcolor='#EF9A9A', shape='component', width='2.5', height='1.2')
        c.node('MCP_Operations', '''🔌 Operations MCP
:8003

Tools:
• scale_deployment
• create_resource''', fillcolor='#EF9A9A', shape='component', width='2.5', height='1.2')
        c.node('MCP_Monitor', '''🔌 Monitor MCP
:8004

Tools:
• query_prometheus
• get_metrics''', fillcolor='#EF9A9A', shape='component', width='2.5', height='1.2')
    
    # Data Source Layer
    with dot.subgraph(name='cluster_sources') as c:
        c.attr(label='💾 DATA SOURCES', style='filled,rounded', color='#E1BEE7', fontsize='15', fontname='Arial Bold', labeljust='l')
        c.node('K8s', '''☸️ Kubernetes Cluster

Master: k8s-master-01 (10.138.0.2)
Worker: k8s-worker-01 (10.138.0.3)

Access: SSH + kubectl commands''', fillcolor='#CE93D8', shape='cylinder', width='3.5', height='1.5')
        c.node('Prometheus', '''📊 Prometheus Server

VM: prometheus-monitoring-01
URL: http://34.53.50.194:9090

Data: node_exporter, cAdvisor,
      kube-state-metrics''', fillcolor='#CE93D8', shape='cylinder', width='3.5', height='1.5')
    
    # User to Supervisor edges
    dot.edge('CLI', 'Supervisor', label='  Query String  ', color='#2196F3', penwidth='2', fontcolor='#2196F3')
    dot.edge('WebUI', 'Supervisor', label='  HTTP Request  ', color='#2196F3', penwidth='2', fontcolor='#2196F3')
    
    # Supervisor to Agents with routing info
    dot.edge('Supervisor', 'HealthAgent', label=' "health" keywords ', color='#4CAF50', penwidth='2', fontcolor='#4CAF50')
    dot.edge('Supervisor', 'DescribeAgent', label=' "describe" keywords ', color='#4CAF50', penwidth='2', fontcolor='#4CAF50')
    dot.edge('Supervisor', 'ResourcesAgent', label=' "resources" keywords ', color='#4CAF50', penwidth='2', fontcolor='#4CAF50')
    dot.edge('Supervisor', 'OperationsAgent', label=' "scale/create" keywords ', color='#4CAF50', penwidth='2', fontcolor='#4CAF50')
    dot.edge('Supervisor', 'MonitorAgent', label=' "metrics/prometheus" ', color='#4CAF50', penwidth='2', fontcolor='#4CAF50')
    
    # Agents to MCP Servers
    dot.edge('HealthAgent', 'MCP_Health', label=' HTTP POST\nMCP Protocol ', color='#FF9800', penwidth='2', style='dashed', fontcolor='#FF9800')
    dot.edge('DescribeAgent', 'MCP_Describe', label=' HTTP POST\nMCP Protocol ', color='#FF9800', penwidth='2', style='dashed', fontcolor='#FF9800')
    dot.edge('ResourcesAgent', 'MCP_Resources', label=' HTTP POST\nMCP Protocol ', color='#FF9800', penwidth='2', style='dashed', fontcolor='#FF9800')
    dot.edge('OperationsAgent', 'MCP_Operations', label=' HTTP POST\nMCP Protocol ', color='#FF9800', penwidth='2', style='dashed', fontcolor='#FF9800')
    dot.edge('MonitorAgent', 'MCP_Monitor', label=' HTTP POST\nMCP Protocol ', color='#FF9800', penwidth='2', style='dashed', fontcolor='#FF9800')
    
    # MCP Servers to Data Sources
    dot.edge('MCP_Health', 'K8s', label=' SSH\nkubectl get pods ', color='#9C27B0', penwidth='2', style='dotted', fontcolor='#9C27B0')
    dot.edge('MCP_Describe', 'K8s', label=' SSH\nkubectl describe ', color='#9C27B0', penwidth='2', style='dotted', fontcolor='#9C27B0')
    dot.edge('MCP_Resources', 'K8s', label=' SSH\nkubectl get nodes ', color='#9C27B0', penwidth='2', style='dotted', fontcolor='#9C27B0')
    dot.edge('MCP_Operations', 'K8s', label=' SSH\nkubectl scale/apply ', color='#9C27B0', penwidth='2', style='dotted', fontcolor='#9C27B0')
    dot.edge('MCP_Monitor', 'Prometheus', label=' HTTP GET\nPromQL Query ', color='#F44336', penwidth='2', style='dotted', fontcolor='#F44336')
    
    st.graphviz_chart(dot)

with tab2:
    st.subheader("🔍 Detailed Flow Examples - One Tool Per Agent")
    
    # Add Supervisor Decision Logic Section
    st.markdown("### 🎯 How Supervisor Routes Queries")
    
    with st.expander("Click to see Supervisor's routing decision process", expanded=True):
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.markdown("#### Supervisor's System Prompt")
            st.code("""
# Supervisor Agent receives:
user_query = "Check pod health in kube-system"

# Claude analyzes query using this prompt:
You are a supervisor routing queries to specialized agents:
- health_agent: Pod status, readiness, liveness checks
- describe_agent: Resource details, configurations
- resources_agent: CPU/memory capacity, limits
- operations_agent: Create, delete, scale resources  
- monitor_agent: Prometheus metrics, real-time data

Analyze the query and route to appropriate agent.
""", language="python")
        
        with col2:
            st.markdown("#### Routing Decision")
            st.code("""
# Claude's reasoning:
Query: "Check pod health in kube-system"

Analysis:
- Contains "health" keyword ✓
- Refers to "pod" status ✓
- About checking current state ✓

Decision: Route to HEALTH_AGENT

Response:
{
  "next": "health_agent",
  "reasoning": "Query asks about pod health status"
}
""", language="json")
    
    st.markdown("---")
    
    # Health Agent Example
    st.markdown("### 1️⃣ Health Agent → `check_pod_health` Tool")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("#### 📝 Tool Definition")
        st.code("""
@mcp.tool()
def check_pod_health(
    namespace: str = "default",
    pod_name: str = ""
) -> str:
    '''Check health status of pods'''
    
    # 1. Build kubectl command
    cmd = f"kubectl get pods -n {namespace} -o json"
    
    # 2. Execute via gcloud SSH to K8s master
    ssh_cmd = (
        f"gcloud compute ssh swinvm15@k8s-master-01 "
        f"--zone=us-west1-a --project=beaming-age-463822-k7 "
        f"--command='{cmd}'"
    )
    result = subprocess.check_output(ssh_cmd, shell=True)
    
    # 3. Parse JSON response
    # Tool PARSES JSON:
    data = json.loads(result)
    pod = data["items"][0]
    
    name = pod["metadata"]["name"]
    status = pod["status"]["phase"]
    ready = "1/1"  # from conditions
    restarts = pod["status"]\\
      ["containerStatuses"][0]\\
      ["restartCount"]
    
    # Tool returns text:
    return f"Pod: {name}\\nStatus: {status}\\nReady: {ready}\\nRestarts: {restarts}"
""", language="python")
    
    with col2:
        st.markdown("#### 🔄 Execution Flow")
        flow = graphviz.Digraph()
        flow.attr(rankdir='TB')
        flow.attr('node', shape='box', style='rounded,filled', fontsize='10', width='3.5')
        
        flow.node('1', '1. User Query\n"Check pod health in kube-system"', fillcolor='#E3F2FD')
        flow.node('2', '2. Supervisor routes to Health Agent\n(keyword: "health")', fillcolor='#C8E6C9')
        flow.node('3', '3. Agent → MCP Client\nHTTP POST to localhost:8000/mcp', fillcolor='#FFF9C4')
        flow.node('4', '4. MCP Server receives request\nParses tool name & parameters', fillcolor='#FFCDD2')
        flow.node('5', '5. Tool executes:\ngcloud ssh to k8s-master-01', fillcolor='#F8BBD0')
        flow.node('6', '6. Run kubectl command:\nkubectl get pods -n kube-system -o json', fillcolor='#E1BEE7')
        flow.node('7', '7. K8s API returns JSON\nwith pod status, conditions', fillcolor='#D1C4E9')
        flow.node('8', '8. Parse JSON → Extract:\nname, status, ready, restarts', fillcolor='#FFCCBC')
        flow.node('9', '9. MCP Server → MCP Client\nHTTP 200 with health data', fillcolor='#C8E6C9')
        flow.node('10', '10. Agent formats response\nReturns to user', fillcolor='#B2DFDB')
        
        flow.edge('1', '2', label='query')
        flow.edge('2', '3', label='tool call')
        flow.edge('3', '4', label='HTTP')
        flow.edge('4', '5', label='invoke')
        flow.edge('5', '6', label='SSH')
        flow.edge('6', '7', label='kubectl')
        flow.edge('7', '8', label='JSON')
        flow.edge('8', '9', label='result')
        flow.edge('9', '10', label='response')
        
        st.graphviz_chart(flow)
    
    st.markdown("#### 📤 MCP Communication Details")
    st.markdown("##### Complete Round-Trip Flow →")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**1️⃣ Agent → MCP Server**")
        st.code("""
POST http://localhost:8000/mcp

{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "check_pod_health",
    "arguments": {
      "namespace": "kube-system"
    }
  }
}
""", language="json")
    
    with col2:
        st.markdown("**2️⃣ MCP Server → Tool**")
        st.code("""
# MCP parses JSON-RPC request
# and invokes tool function:

check_pod_health(
    namespace="kube-system",
    pod_name=""
)
""", language="python")
    
    with col3:
        st.markdown("**3️⃣ Tool → K8s Cluster**")
        st.code("""
# Tool executes:
gcloud compute ssh \\
  swinvm15@k8s-master-01 \\
  --zone=us-west1-a \\
  --command="kubectl get pods \\
    -n kube-system -o json"
""", language="bash")
    
    col4, col5, col6 = st.columns(3)
    
    with col4:
        st.markdown("**4️⃣ K8s Cluster → Tool**")
        st.code("""
# K8s returns RAW JSON:
{
  "items": [{
    "metadata": {
      "name": "coredns-xxx"
    },
    "status": {
      "phase": "Running",
      "conditions": [{
        "type": "Ready",
        "status": "True"
      }],
      "containerStatuses": [{
        "restartCount": 0
      }]
    }
  }]
}
""", language="json")
    
    with col5:
        st.markdown("**5️⃣ Tool Parses → MCP Server**")
        st.code("""
# Tool PARSES JSON:
data = json.loads(output)
pod = data["items"][0]

name = pod["metadata"]["name"]
status = pod["status"]["phase"]
ready = "1/1"  # from conditions
restarts = pod["status"]\\
  ["containerStatuses"][0]\\
  ["restartCount"]

# Tool returns text:
return f\"\"\"Pod: {name}
Status: {status}
Ready: {ready}
Restarts: {restarts}\"\"\"
""", language="python")
    
    with col6:
        st.markdown("**6️⃣ MCP Server → Agent**")
        st.code("""
# MCP wraps tool output:
{
  "jsonrpc": "2.0",
  "result": {
    "content": [{
      "type": "text",
      "text": "Pod: coredns-xxx
Status: Running
Ready: 1/1
Restarts: 0"
    }]
  }
}

# Agent extracts:
text = response["result"]\\
  ["content"][0]["text"]
""", language="json")
    
    st.markdown("---")
    
    # Describe Agent Example
    st.markdown("### 2️⃣ Describe Agent → `describe_resource` Tool")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("#### 📝 Tool Definition")
        st.code("""
@mcp.tool()
def describe_resource(
    resource_type: str,
    resource_name: str,
    namespace: str = "default"
) -> str:
    '''Get detailed info about a resource'''
    
    # 1. Build kubectl describe command
    cmd = f"kubectl describe {resource_type} {resource_name}"
    cmd += f" -n {namespace}"
    
    # 2. Execute via gcloud SSH to K8s master
    ssh_cmd = (
        f"gcloud compute ssh swinvm15@k8s-master-01 "
        f"--zone=us-west1-a --project=beaming-age-463822-k7 "
        f"--command='{cmd}'"
    )
    result = subprocess.check_output(ssh_cmd, shell=True)
    
    # 3. Read output (detailed description)
    output = result.decode()
    
    # kubectl describe returns human-readable text (NOT JSON)
    # No parsing needed - just return as-is:
    return output
    
    # Output contains:
    # - Name, Namespace, Labels
    # - Status, Conditions
    # - Container specs, Volumes
    # - Events (last 10 minutes)
    
    # 4. Return raw output
    return output
""", language="python")
    
    with col2:
        st.markdown("#### 🔄 Execution Flow")
        flow2 = graphviz.Digraph()
        flow2.attr(rankdir='TB')
        flow2.attr('node', shape='box', style='rounded,filled', fontsize='10', width='3.5')
        
        flow2.node('1', '1. User Query\n"Describe pod coredns-xxx"', fillcolor='#E3F2FD')
        flow2.node('2', '2. Supervisor routes to Describe Agent\n(keyword: "describe")', fillcolor='#C8E6C9')
        flow2.node('3', '3. Agent → MCP Client\nHTTP POST to localhost:8002/mcp', fillcolor='#FFF9C4')
        flow2.node('4', '4. MCP Server receives request\nExtracts: type=pod, name=coredns-xxx', fillcolor='#FFCDD2')
        flow2.node('5', '5. Tool executes:\ngcloud ssh to k8s-master-01', fillcolor='#F8BBD0')
        flow2.node('6', '6. Run kubectl describe:\nkubectl describe pod coredns-xxx', fillcolor='#E1BEE7')
        flow2.node('7', '7. K8s returns full description:\nspec, status, events', fillcolor='#D1C4E9')
        flow2.node('8', '8. MCP Server formats output\nReturns complete description', fillcolor='#FFCCBC')
        flow2.node('9', '9. Agent receives text\nPasses to Claude for analysis', fillcolor='#C8E6C9')
        flow2.node('10', '10. User gets formatted\nresource description', fillcolor='#B2DFDB')
        
        flow2.edge('1', '2')
        flow2.edge('2', '3')
        flow2.edge('3', '4')
        flow2.edge('4', '5')
        flow2.edge('5', '6')
        flow2.edge('6', '7')
        flow2.edge('7', '8')
        flow2.edge('8', '9')
        flow2.edge('9', '10')
        
        st.graphviz_chart(flow2)
    
    st.markdown("#### 📤 Example Response")
    st.text("""
Name:         coredns-5dd5756b68-bhkdv
Namespace:    kube-system
Node:         k8s-master-01
Status:       Running
IP:           10.244.0.2
Containers:
  coredns:
    Image:      registry.k8s.io/coredns/coredns:v1.11.1
    Port:       53/UDP, 53/TCP
    State:      Running
    """)
    
    # MCP Communication details for Describe Agent
    with st.expander("📡 MCP Communication Details - Describe Agent"):
        st.markdown("**Complete Round-Trip Flow →**")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("**1️⃣ Agent → MCP Server**")
            st.code('''POST http://localhost:8002/mcp

{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "describe_resource",
    "arguments": {
      "resource_type": "pod",
      "resource_name": "coredns-xxx",
      "namespace": "kube-system"
    }
  }
}''', language='json')
        
        with col2:
            st.markdown("**2️⃣ MCP Server → Tool**")
            st.code('''# MCP parses and invokes:

describe_resource(
    resource_type="pod",
    resource_name="coredns-xxx",
    namespace="kube-system"
)''', language='python')
        
        with col3:
            st.markdown("**3️⃣ Tool → K8s Cluster**")
            st.code('''# Tool executes:
gcloud compute ssh \\
  swinvm15@k8s-master-01 \\
  --zone=us-west1-a \\
  --command="kubectl describe \\
    pod coredns-xxx \\
    -n kube-system"''', language='bash')
        
        col4, col5, col6 = st.columns(3)
        
        with col4:
            st.markdown("**4️⃣ K8s Cluster → Tool**")
            st.code('''# K8s returns RAW TEXT:
Name:       coredns-xxx
Namespace:  kube-system
Node:       k8s-master-01
Status:     Running
IP:         10.244.0.2
Containers:
  coredns:
    Image:  coredns:v1.11.1
    State:  Running
Events:     <none>''', language='text')
        
        with col5:
            st.markdown("**5️⃣ Tool Returns → MCP Server**")
            st.code('''# Tool returns text as-is
# (kubectl describe already
# gives human-readable format)

return output
# No JSON parsing needed!

# Returns complete description
# text to MCP Server''', language='python')
        
        with col6:
            st.markdown("**6️⃣ MCP Server → Agent**")
            st.code('''# MCP wraps tool output:
{
  "jsonrpc": "2.0",
  "result": {
    "content": [{
      "type": "text",
      "text": "Name: coredns-xxx
Namespace: kube-system
Status: Running
IP: 10.244.0.2..."
    }]
  }
}

# Agent extracts:
text = response["result"]\\
  ["content"][0]["text"]''', language='json')
    
    st.markdown("---")
    
    # Resources Agent Example
    st.markdown("### 3️⃣ Resources Agent → `get_node_resources` Tool")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("#### 📝 Tool Definition")
        st.code("""
@mcp.tool()
def get_node_resources() -> str:
    '''Get CPU and memory capacity of nodes'''
    
    # 1. Build kubectl command for node resources
    cmd = "kubectl get nodes -o json"
    
    # 2. Execute via gcloud SSH to K8s master
    ssh_cmd = (
        f"gcloud compute ssh swinvm15@k8s-master-01 "
        f"--zone=us-west1-a --project=beaming-age-463822-k7 "
        f"--command='{cmd}'"
    )
    result = subprocess.check_output(ssh_cmd, shell=True).decode()
    
    # 3. Parse JSON to extract capacity/allocatable
    # Tool PARSES JSON:
    data = json.loads(result)
    node = data["items"][0]
    
    name = node["metadata"]["name"]
    cpu = node["status"]["capacity"]["cpu"]
    mem_ki = node["status"]["capacity"]\\
      ["memory"]
    
    # Convert Ki to GiB:
    mem_gib = int(mem_ki.replace('Ki', ''))\\
      / 1024 / 1024
    
    # Tool returns text:
    return f"{name}:\\n    CPU: {cpu} cores\\n    Memory: {mem_gib:.1f} GiB"
""", language="python")
    
    with col2:
        st.markdown("#### 🔄 Execution Flow")
        flow3 = graphviz.Digraph()
        flow3.attr(rankdir='TB')
        flow3.attr('node', shape='box', style='rounded,filled', fontsize='10', width='3.5')
        
        flow3.node('1', '1. User Query\n"Show node resources"', fillcolor='#E3F2FD')
        flow3.node('2', '2. Supervisor routes to Resources Agent\n(keyword: "resources")', fillcolor='#C8E6C9')
        flow3.node('3', '3. Agent → MCP Client\nHTTP POST to localhost:8001/mcp', fillcolor='#FFF9C4')
        flow3.node('4', '4. MCP Server receives request\nPrepares kubectl command', fillcolor='#FFCDD2')
        flow3.node('5', '5. Tool executes:\ngcloud ssh to k8s-master-01', fillcolor='#F8BBD0')
        flow3.node('6', '6. Run: kubectl get nodes -o json\nGet all node specs', fillcolor='#E1BEE7')
        flow3.node('7', '7. K8s returns node data:\ncapacity, allocatable fields', fillcolor='#D1C4E9')
        flow3.node('8', '8. Parse each node:\nextract CPU, memory, storage', fillcolor='#FFCCBC')
        flow3.node('9', '9. MCP Server → Agent\nJSON with resource summary', fillcolor='#C8E6C9')
        flow3.node('10', '10. Agent formats output\nShows capacity vs allocatable', fillcolor='#B2DFDB')
        
        flow3.edge('1', '2')
        flow3.edge('2', '3')
        flow3.edge('3', '4')
        flow3.edge('4', '5')
        flow3.edge('5', '6')
        flow3.edge('6', '7')
        flow3.edge('7', '8')
        flow3.edge('8', '9')
        flow3.edge('9', '10')
        
        st.graphviz_chart(flow3)
    
    # MCP Communication details for Resources Agent
    with st.expander("📡 MCP Communication Details - Resources Agent"):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("**1️⃣ Agent → MCP Server**")
            st.code("""
POST http://localhost:8002/mcp

{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "get_node_resources",
    "arguments": {}
  }
}
""", language="json")
        
        with col2:
            st.markdown("**2️⃣ MCP Server → Tool**")
            st.code("""
# MCP parses JSON-RPC request
# and invokes tool function:

get_node_resources()
""", language="python")
        
        with col3:
            st.markdown("**3️⃣ Tool → K8s Cluster**")
            st.code("""
# Tool executes:
gcloud compute ssh \\
  swinvm15@k8s-master-01 \\
  --zone=us-west1-a \\
  --command="kubectl get nodes \\
    -o json"
""", language="bash")
        
        col4, col5, col6 = st.columns(3)
        
        with col4:
            st.markdown("**4️⃣ K8s Cluster → Tool**")
            st.code("""
# K8s returns RAW JSON:
{
  "items": [{
    "metadata": {
      "name": "k8s-master-01"
    },
    "status": {
      "capacity": {
        "cpu": "2",
        "memory": "3926600Ki"
      },
      "allocatable": {
        "cpu": "2",
        "memory": "3824200Ki"
      }
    }
  }]
}
""", language="json")
        
        with col5:
            st.markdown("**5️⃣ Tool Parses → MCP Server**")
            st.code("""
# Tool PARSES JSON:
data = json.loads(output)
node = data["items"][0]

name = node["metadata"]["name"]
cpu = node["status"]["capacity"]["cpu"]
mem_ki = node["status"]["capacity"]\\
  ["memory"]

# Convert Ki to GiB:
mem_gib = int(mem_ki.replace('Ki', ''))\\
  / 1024 / 1024

# Tool returns text:
return f\"\"\"{name}:
    CPU: {cpu} cores
    Memory: {mem_gib:.1f} GiB\"\"\"
""", language="python")
        
        with col6:
            st.markdown("**6️⃣ MCP Server → Agent**")
            st.code("""
# MCP wraps tool output:
{
  "jsonrpc": "2.0",
  "result": {
    "content": [{
      "type": "text",
      "text": "k8s-master-01:
    CPU: 2 cores
    Memory: 3.7 GiB
k8s-worker-01:
    CPU: 2 cores
    Memory: 3.7 GiB"
    }]
  }
}

# Agent extracts:
text = response["result"]\\
  ["content"][0]["text"]
""", language="json")
    
    st.markdown("#### 📤 Example Response")
    st.json([
        {
            "name": "k8s-master-01",
            "cpu": "2",
            "memory": "4007084Ki",
            "allocatable_cpu": "2",
            "allocatable_memory": "3884492Ki"
        },
        {
            "name": "k8s-worker-01",
            "cpu": "2",
            "memory": "4007076Ki",
            "allocatable_cpu": "2",
            "allocatable_memory": "3884484Ki"
        }
    ])
    
    st.markdown("---")
    
    # Operations Agent Example
    st.markdown("### 4️⃣ Operations Agent → `scale_deployment` Tool")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("#### 📝 Tool Definition")
        st.code("""
@mcp.tool()
def scale_deployment(
    deployment_name: str,
    replicas: int,
    namespace: str = "default"
) -> str:
    '''Scale a deployment to specified replicas'''
    
    # 1. Build kubectl scale command
    cmd = f"kubectl scale deployment {deployment_name}"
    cmd += f" --replicas={replicas} -n {namespace}"
    
    # 2. Execute via gcloud SSH to K8s master
    ssh_cmd = (
        f"gcloud compute ssh swinvm15@k8s-master-01 "
        f"--zone=us-west1-a --project=beaming-age-463822-k7 "
        f"--command='{cmd}'"
    )
    scale_result = subprocess.check_output(ssh_cmd, shell=True).decode()
    # Output: "deployment.apps/nginx scaled"
    
    # 3. Verify the scaling worked
    verify_cmd = f"kubectl get deployment {deployment_name}"
    verify_cmd += f" -n {namespace} -o json"
    stdin, stdout, stderr = ssh_client.exec_command(verify_cmd)
    
    # Tool PARSES JSON:
    data = json.loads(output)
    
    name = data["metadata"]["name"]
    desired = data["spec"]["replicas"]
    current = data["status"]["replicas"]
    ready = data["status"]\\
      ["readyReplicas"]
    
    # Tool returns text:
    return f"Successfully scaled deployment {name} to {desired} replicas.\\nCurrent status: {ready}/{current} ready"
""", language="python")
    
    with col2:
        st.markdown("#### 🔄 Execution Flow")
        flow4 = graphviz.Digraph()
        flow4.attr(rankdir='TB')
        flow4.attr('node', shape='box', style='rounded,filled', fontsize='10', width='3.5')
        
        flow4.node('1', '1. User Command\n"Scale deployment to 3 replicas"', fillcolor='#E3F2FD')
        flow4.node('2', '2. Supervisor routes to Operations Agent\n(keyword: "scale")', fillcolor='#C8E6C9')
        flow4.node('3', '3. Agent → MCP Client\nHTTP POST to localhost:8003/mcp', fillcolor='#FFF9C4')
        flow4.node('4', '4. MCP Server receives:\nname, replicas, namespace', fillcolor='#FFCDD2')
        flow4.node('5', '5. Tool executes:\ngcloud ssh to k8s-master-01', fillcolor='#F8BBD0')
        flow4.node('6', '6. Run: kubectl scale deployment\n--replicas=3', fillcolor='#E1BEE7')
        flow4.node('7', '7. K8s applies changes:\nupdates ReplicaSet', fillcolor='#D1C4E9')
        flow4.node('8', '8. Verify with kubectl get:\ncheck current vs desired', fillcolor='#FFCCBC')
        flow4.node('9', '9. MCP Server → Agent\nConfirmation with status', fillcolor='#C8E6C9')
        flow4.node('10', '10. Agent returns success:\nScaled to 3, Ready: 3/3', fillcolor='#B2DFDB')
        
        flow4.edge('1', '2')
        flow4.edge('2', '3')
        flow4.edge('3', '4')
        flow4.edge('4', '5')
        flow4.edge('5', '6')
        flow4.edge('6', '7')
        flow4.edge('7', '8')
        flow4.edge('8', '9')
        flow4.edge('9', '10')
        
        st.graphviz_chart(flow4)
    
    # MCP Communication details for Operations Agent
    with st.expander("📡 MCP Communication Details - Operations Agent"):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("**1️⃣ Agent → MCP Server**")
            st.code("""
POST http://localhost:8003/mcp

{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "scale_deployment",
    "arguments": {
      "deployment_name": "nginx",
      "replicas": 3,
      "namespace": "default"
    }
  }
}
""", language="json")
        
        with col2:
            st.markdown("**2️⃣ MCP Server → Tool**")
            st.code("""
# MCP parses JSON-RPC request
# and invokes tool function:

scale_deployment(
    deployment_name="nginx",
    replicas=3,
    namespace="default"
)
""", language="python")
        
        with col3:
            st.markdown("**3️⃣ Tool → K8s Cluster**")
            st.code("""
# Tool executes:
gcloud compute ssh \\
  swinvm15@k8s-master-01 \\
  --zone=us-west1-a \\
  --command="kubectl scale \\
    deployment nginx \\
    --replicas=3 -n default && \\
    kubectl get deployment nginx \\
    -n default -o json"
""", language="bash")
        
        col4, col5, col6 = st.columns(3)
        
        with col4:
            st.markdown("**4️⃣ K8s Cluster → Tool**")
            st.code("""
# K8s returns RAW JSON:
{
  "metadata": {
    "name": "nginx"
  },
  "spec": {
    "replicas": 3
  },
  "status": {
    "replicas": 3,
    "readyReplicas": 3,
    "availableReplicas": 3
  }
}
""", language="json")
        
        with col5:
            st.markdown("**5️⃣ Tool Parses → MCP Server**")
            st.code("""
# Tool PARSES JSON:
data = json.loads(output)

name = data["metadata"]["name"]
desired = data["spec"]["replicas"]
current = data["status"]["replicas"]
ready = data["status"]\\
  ["readyReplicas"]

# Tool returns text:
return f\"\"\"Successfully scaled \\
deployment {name} to {desired} \\
replicas.
Current status: {ready}/{current} \\
ready\"\"\"
""", language="python")
        
        with col6:
            st.markdown("**6️⃣ MCP Server → Agent**")
            st.code("""
# MCP wraps tool output:
{
  "jsonrpc": "2.0",
  "result": {
    "content": [{
      "type": "text",
      "text": "Successfully scaled deployment nginx to 3 replicas.
Current status: 3/3 ready"
    }]
  }
}

# Agent extracts:
text = response["result"]\\
  ["content"][0]["text"]
""", language="json")
    
    st.markdown("#### 📤 Example Response")
    st.text("""
deployment.apps/nginx-deployment scaled

NAME               READY   UP-TO-DATE   AVAILABLE   AGE
nginx-deployment   3/3     3            3           10m
    """)
    
    st.markdown("---")
    
    # Monitor Agent Example
    st.markdown("### 5️⃣ Monitor Agent → `query_prometheus_instant` Tool")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("#### 📝 Tool Definition")
        st.code("""
@mcp.tool()
def query_prometheus_instant(
    query: str,
    time: str = ""
) -> str:
    '''Execute instant Prometheus query'''
    
    # 1. Build Prometheus API URL
    PROMETHEUS_URL = "http://34.53.50.194:9090"
    url = f"{PROMETHEUS_URL}/api/v1/query"
    
    # 2. Prepare query parameters
    params = {"query": query}
    if time:
        params["time"] = time  # Unix timestamp
    
    # Example query:
    # "node_memory_MemTotal_bytes" - Total memory
    # "100 - (node_memory_MemAvailable_bytes / 
    #         node_memory_MemTotal_bytes * 100)" - Memory usage %
    
    # 3. Execute HTTP GET request
    response = requests.get(url, params=params, timeout=10)
    
    # 4. Parse JSON response
    # Tool PARSES JSON:
    data = response.json()
    results = data["data"]["result"]
    
    metrics = []
    for r in results:
        instance = r["metric"]["instance"]
        # e.g. "10.138.0.2:9100"
        
        value = r["value"][1]
        # e.g. "15.23"
        
        # Map IP to node name:
        node = map_ip_to_node(instance)
        
        metrics.append(
          f"{node}: {value}%")
    
    # Tool returns text:
    return '\\n'.join(metrics)
""", language="python")
    
    with col2:
        st.markdown("#### 🔄 Execution Flow")
        flow5 = graphviz.Digraph()
        flow5.attr(rankdir='TB')
        flow5.attr('node', shape='box', style='rounded,filled', fontsize='10', width='3.5')
        
        flow5.node('1', '1. User Query\n"Show me CPU usage"', fillcolor='#E3F2FD')
        flow5.node('2', '2. Supervisor routes to Monitor Agent\n(keyword: "CPU usage")', fillcolor='#C8E6C9')
        flow5.node('3', '3. Agent → MCP Client\nHTTP POST to localhost:8004/mcp', fillcolor='#FFF9C4')
        flow5.node('4', '4. MCP Server receives request\nBuilds PromQL query', fillcolor='#FFCDD2')
        flow5.node('5', '5. Tool executes:\nHTTP GET to Prometheus', fillcolor='#F8BBD0')
        flow5.node('6', '6. Query Prometheus API:\n/api/v1/query?query=node_cpu...', fillcolor='#E1BEE7')
        flow5.node('7', '7. Prometheus returns metrics:\nJSON with instance, value pairs', fillcolor='#D1C4E9')
        flow5.node('8', '8. Parse metrics data:\nExtract instance & percentage', fillcolor='#FFCCBC')
        flow5.node('9', '9. MCP Server → Agent\nReturns formatted metrics', fillcolor='#C8E6C9')
        flow5.node('10', '10. Agent formats for user:\nmaster: 13%, worker: 7%', fillcolor='#B2DFDB')
        
        flow5.edge('1', '2')
        flow5.edge('2', '3')
        flow5.edge('3', '4')
        flow5.edge('4', '5')
        flow5.edge('5', '6')
        flow5.edge('6', '7')
        flow5.edge('7', '8')
        flow5.edge('8', '9')
        flow5.edge('9', '10')
        
        st.graphviz_chart(flow5)
    
    st.markdown("#### 📤 MCP Communication & Prometheus Query")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**1️⃣ Agent → MCP Server**")
        st.code("""
POST http://localhost:8004/mcp

{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "query_prometheus_instant",
    "arguments": {
      "query": "100 - (avg by(instance) 
        (rate(node_cpu_seconds_total
        {mode='idle'}[5m])) * 100)"
    }
  }
}
""", language="json")
    
    with col2:
        st.markdown("**2️⃣ MCP Server → Tool**")
        st.code("""
# MCP parses JSON-RPC request
# and invokes tool function:

query_prometheus_instant(
    query="100 - (avg by(instance) 
      (rate(node_cpu_seconds_total
      {mode='idle'}[5m])) * 100)"
)
""", language="python")
    
    with col3:
        st.markdown("**3️⃣ Tool → Prometheus**")
        st.code("""
# Tool executes HTTP request:
GET http://34.53.50.194:9090\\
  /api/v1/query

Query params:
query=100 - (avg by(instance)\\
  (rate(node_cpu_seconds_total\\
  {mode='idle'}[5m])) * 100)
""", language="bash")
    
    col4, col5, col6 = st.columns(3)
    
    with col4:
        st.markdown("**4️⃣ Prometheus → Tool**")
        st.code("""
# Prometheus returns RAW JSON:
{
  "status": "success",
  "data": {
    "resultType": "vector",
    "result": [
      {
        "metric": {
          "instance": "10.138.0.2:9100"
        },
        "value": [1234567, "15.23"]
      },
      {
        "metric": {
          "instance": "10.138.0.3:9100"
        },
        "value": [1234567, "8.45"]
      }
    ]
  }
}
""", language="json")
    
    with col5:
        st.markdown("**5️⃣ Tool Parses → MCP Server**")
        st.code("""
# Tool PARSES JSON:
data = response.json()
results = data["data"]["result"]

metrics = []
for r in results:
    instance = r["metric"]["instance"]
    # e.g. "10.138.0.2:9100"
    
    value = r["value"][1]
    # e.g. "15.23"
    
    # Map IP to node name:
    node = map_ip_to_node(instance)
    
    metrics.append(
      f"{node}: {value}%")

# Tool returns text:
return '\\n'.join(metrics)
""", language="python")
    
    with col6:
        st.markdown("**6️⃣ MCP Server → Agent**")
        st.code("""
# MCP wraps tool output:
{
  "jsonrpc": "2.0",
  "result": {
    "content": [{
      "type": "text",
      "text": "k8s-master-01: 15.23%
k8s-worker-01: 8.45%"
    }]
  }
}

# Agent extracts:
text = response["result"]\\
  ["content"][0]["text"]
""", language="json")

with tab3:
    st.subheader("📖 Component Glossary")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 🎯 Supervisor Agent")
        st.info("""
        **Role:** Query router and orchestrator
        
        **Technology:** LangGraph workflow with Claude Sonnet 4.5
        
        **Function:** Analyzes user queries and routes them to the appropriate specialized agent. 
        Maintains conversation context and combines responses from multiple agents when needed.
        """)
        
        st.markdown("#### ❤️ Health Agent")
        st.info("""
        **Specialization:** Pod health monitoring
        
        **Tools:** check_pod_health, check_pod_readiness, check_pod_liveness
        
        **Data Source:** Kubernetes API via kubectl
        """)
        
        st.markdown("#### 📋 Describe Agent")
        st.info("""
        **Specialization:** Resource details and configurations
        
        **Tools:** describe_resource, get_resource_yaml, get_resource_events
        
        **Data Source:** Kubernetes API via kubectl describe/get
        """)
        
        st.markdown("#### 📊 Resources Agent")
        st.info("""
        **Specialization:** Capacity planning and resource allocation
        
        **Tools:** get_node_resources, get_pod_resources, get_namespace_quota
        
        **Data Source:** Kubernetes API via kubectl
        """)
    
    with col2:
        st.markdown("#### ⚙️ Operations Agent")
        st.info("""
        **Specialization:** Cluster modifications
        
        **Tools:** scale_deployment, create_resource, delete_resource, apply_yaml
        
        **Data Source:** Kubernetes API via kubectl (write operations)
        """)
        
        st.markdown("#### 📈 Monitor Agent")
        st.info("""
        **Specialization:** Real-time metrics and monitoring
        
        **Tools:** query_prometheus_instant, query_prometheus_range, get_node_metrics, get_pod_metrics
        
        **Data Source:** Prometheus HTTP API (PromQL queries)
        """)
        
        st.markdown("#### 🔌 MCP Servers")
        st.info("""
        **Technology:** FastMCP (Model Context Protocol)
        
        **Protocol:** HTTP/JSON over ports 8000-8004
        
        **Function:** Expose tools as API endpoints that agents can call. Handle authentication, 
        command execution, and response formatting.
        """)
        
        st.markdown("#### ☸️ Kubernetes Cluster")
        st.info("""
        **Access Method:** SSH to master node + kubectl commands
        
        **Components:** 2 nodes (master + worker), various system pods
        
        **Monitoring:** node_exporter, cAdvisor, kube-state-metrics
        """)
        
        st.markdown("#### 📊 Prometheus")
        st.info("""
        **Location:** prometheus-monitoring-01 VM (34.53.50.194:9090)
        
        **Scrapers:** node_exporter (node metrics), cAdvisor (container metrics), 
        kube-state-metrics (K8s object state)
        
        **Access:** HTTP API with PromQL query language
        """)

# Add a section showing the MCP Protocol details
st.markdown("---")
st.subheader("🔗 MCP Protocol Communication")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("#### 1️⃣ Agent → MCP Server")
    st.code("""
POST http://localhost:8000/mcp
Content-Type: application/json

{
  "method": "tools/call",
  "params": {
    "name": "check_pod_health",
    "arguments": {
      "namespace": "kube-system"
    }
  }
}
    """, language="json")

with col2:
    st.markdown("#### 2️⃣ MCP Server → K8s/Prometheus")
    st.code("""
# For Kubernetes tools:
SSH swinvm15@k8s-master-01
→ kubectl get pods -n kube-system -o json

# For Prometheus tools:
GET http://34.53.50.194:9090/api/v1/query
→ ?query=up
    """, language="bash")

with col3:
    st.markdown("#### 3️⃣ MCP Server → Agent")
    st.code("""
HTTP/1.1 200 OK
Content-Type: application/json

{
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Pod health report..."
      }
    ]
  }
}
    """, language="json")

# Footer with key insights
st.markdown("---")
st.success("""
### 🎯 Key Architecture Insights:

1. **Separation of Concerns:** Each agent specializes in one domain (health, operations, monitoring, etc.)
2. **MCP Protocol:** Standardized communication between agents and tools via HTTP/JSON
3. **Multiple Data Sources:** Kubernetes (via SSH + kubectl) and Prometheus (via HTTP API)
4. **Supervisor Pattern:** Single entry point routes queries intelligently to specialized agents
5. **Scalable Design:** Easy to add new agents or tools without modifying existing components
""")

st.info("""
💡 **Want to see this in action?** Try these queries in the CLI:
- `"Check health of all pods in kube-system"`
- `"Show me CPU usage from Prometheus"`
- `"Scale my deployment to 5 replicas"`
""")
