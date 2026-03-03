"""
Resources Agent - CPU/memory capacity and usage monitoring
Handles queries about resource allocation, limits, requests, and utilization
Uses MCP Server for tool execution
"""

import os
import asyncio
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, MessagesState
from langchain_mcp_adapters.client import MultiServerMCPClient

# Load environment variables
load_dotenv()

# Cache for compiled workflow to avoid recreating on every query
_cached_workflow = None
_cached_api_key = None
_cache_version = 13  # Increment this to force workflow recreation


def _is_disk_question(text: str) -> bool:
    if not text:
        return False
    return any(k in text.lower() for k in ["disk", "storage", "ephemeral", "volume", "pvc", "filesystem"])


def _is_all_pod_resources_question(text: str) -> bool:
    """Detect: user wants ALL resource fields for pods/deployments (limits + requests together),
    OR is asking generically about 'resource limits' / 'resource requests' without specifying one field."""
    if not text:
        return False
    q = text.lower()
    has_workload = any(k in q for k in ["pod", "pods", "container", "deployment", "deployments", "daemonset", "statefulset"])
    has_limit    = "limit" in q or "limits" in q
    has_request  = "request" in q or "requests" in q
    # Explicit: user asked for both limits AND requests
    if has_workload and has_limit and has_request:
        return True
    # Generic: "resource limits" or "resource requests" without singling out cpu/memory
    has_resource_qualifier = "resource limit" in q or "resource limits" in q or "resource request" in q or "resource requests" in q
    no_specific_field = "cpu" not in q and "memory" not in q and "mem " not in q
    if has_workload and has_resource_qualifier and no_specific_field:
        return True
    return False


def _is_single_field_pod_question(text: str):
    """
    Detect: user wants ONE specific field for pods/deployments.
    Returns (field, namespace) tuple or None.
    """
    if not text:
        return None
    q = text.lower()
    workload_keywords = ["pod", "pods", "container", "deployment", "deployments", "daemonset", "statefulset"]
    if not any(k in q for k in workload_keywords):
        return None
    ns = "all" if "all namespace" in q or "all ns" in q or "across" in q else "default"
    if ("cpu limit" in q or "cpu limits" in q) and "memory" not in q and "request" not in q:
        return ("cpu_limits", ns)
    if ("memory limit" in q or "memory limits" in q or "mem limit" in q) and "cpu" not in q and "request" not in q:
        return ("memory_limits", ns)
    if ("cpu request" in q or "cpu requests" in q) and "memory" not in q and "limit" not in q:
        return ("cpu_requests", ns)
    if ("memory request" in q or "memory requests" in q or "mem request" in q) and "cpu" not in q and "limit" not in q:
        return ("memory_requests", ns)
    return None


def _is_pod_comparison_question(text: str) -> bool:
    """Detect: user wants to find the pod with highest/most memory or CPU (comparison)."""
    if not text:
        return False
    q = text.lower()
    has_comparison = any(k in q for k in ["highest", "most", "largest", "top", "biggest", "max", "consuming the most", "uses most", "using most"])
    has_resource = any(k in q for k in ["memory", "cpu", "mem"])
    has_pod = any(k in q for k in ["pod", "pods", "container"])
    return has_comparison and has_resource and has_pod


def _is_namespace_resources_question(text: str) -> bool:
    """Detect: user asking for resource allocation per/by namespace."""
    if not text:
        return False
    q = text.lower()
    has_ns = "namespace" in q or "namespaces" in q
    has_resource = any(k in q for k in ["resource", "allocated", "allocation", "cpu", "memory", "request", "limit"])
    return has_ns and has_resource


def _is_total_resource_question(text: str) -> bool:
    """Detect: user wants an aggregate total (sum) of a resource across pods."""
    if not text:
        return False
    q = text.lower()
    return "total" in q and any(k in q for k in ["memory", "cpu", "mem"]) and any(k in q for k in ["request", "requests", "limit", "limits"])


def _append_total(per_pod_output: str, field: str) -> str:
    """
    Parse per-pod output from get_pod_specific_resource and append a summed total.
    Handles Mi, Gi, Ki for memory and m (millicores) for CPU.
    """
    import re
    lines = per_pod_output.strip().splitlines()
    total_mib = 0.0
    total_mc  = 0.0
    is_memory = "memory" in field or "mem" in field

    for line in lines:
        match = re.search(r':\s*(\d+(?:\.\d+)?)\s*(Mi|Gi|Ki|m)?', line)
        if not match:
            continue
        val, unit = float(match.group(1)), match.group(2) or ""
        if is_memory:
            if unit == "Mi":   total_mib += val
            elif unit == "Gi": total_mib += val * 1024
            elif unit == "Ki": total_mib += val / 1024
        else:
            if unit == "m":    total_mc += val
            else:              total_mc += val * 1000

    if is_memory:
        total_str = (f"{total_mib / 1024:.2f} GiB ({total_mib:.0f} MiB)"
                     if total_mib >= 1024 else f"{total_mib:.0f} MiB")
    else:
        total_str = (f"{total_mc / 1000:.2f} cores ({total_mc:.0f}m)"
                     if total_mc >= 1000 else f"{total_mc:.0f}m")

    return per_pod_output.rstrip() + (
        f"\n\n─────────────────────────────"
        f"\nTotal: {total_str}"
        f"\n(excludes pods with 'not set')"
    )


def _is_pods_without_limits_question(text: str) -> bool:
    """Detect: user asking which pods are missing limits or requests."""
    if not text:
        return False
    q = text.lower()
    has_workload = any(k in q for k in ["pod", "pods", "container", "deployment", "deployments"])
    has_limit_or_request = "limit" in q or "limits" in q or "request" in q or "requests" in q
    missing_signals = ["don't have", "do not have", "without", "no limit", "no request",
                       "missing", "not defined", "not set", "undefined", "lacking"]
    return has_workload and has_limit_or_request and any(s in q for s in missing_signals)


def _extract_pods_without_limits(table_output: str) -> str:
    """
    Parse get_pod_resources table output and return only pods that have
    'not set' for CPU Limit or Mem Limit.
    Table format (fixed-width):
      {pod:<55} {cpu_lim:<12} {mem_lim:<12} {cpu_req:<14} {mem_req:<12}
    """
    lines = table_output.strip().splitlines()
    missing = []
    # First 3 lines are: title, header row, separator — skip them
    for line in lines[3:]:
        if not line.strip():
            continue
        pod_name = line[:55].strip()
        cpu_lim  = line[56:68].strip() if len(line) > 56 else ""
        mem_lim  = line[69:81].strip() if len(line) > 69 else ""
        if not pod_name:
            continue
        no_cpu = cpu_lim == "not set" or cpu_lim == ""
        no_mem = mem_lim == "not set" or mem_lim == ""
        if no_cpu or no_mem:
            missing.append((pod_name, "not set" if no_cpu else cpu_lim, "not set" if no_mem else mem_lim))

    if not missing:
        return "All pods have resource limits defined."

    result  = f"Pods with missing resource limits ({len(missing)} found):\n\n"
    result += f"{'Pod':<55} {'CPU Limit':<12} {'Mem Limit':<12}\n"
    result += "-" * 79 + "\n"
    for pod, cpu, mem in missing:
        result += f"{pod:<55} {cpu:<12} {mem:<12}\n"
    return result


async def _get_mcp_tools():
    """Get tools from MCP Resources Server"""
    client = MultiServerMCPClient(
        {
            "k8s_resources": {
                "transport": "streamable_http",
                "url": "http://127.0.0.1:8001/mcp"
            }
        }
    )
    tools = await client.get_tools()
    return tools


# ============================================================================
# RESOURCES AGENT CREATION
# ============================================================================

def create_resources_agent(api_key: str = None, verbose: bool = False):
    """
    Create the Resources Agent for CPU/memory capacity and usage monitoring using MCP Server.
    
    Args:
        api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
        verbose: Whether to show agent reasoning steps
    
    Returns:
        Compiled LangGraph workflow
    """
    # Get API key
    anthropic_api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
    if not anthropic_api_key:
        raise ValueError("Anthropic API key required. Set ANTHROPIC_API_KEY environment variable.")
    
    # Fetch tools from MCP server
    tools = asyncio.run(_get_mcp_tools())
    
    # Initialize Claude model
    model = ChatAnthropic(
        model="claude-3-haiku-20240307",
        anthropic_api_key=anthropic_api_key,
        temperature=0,
        max_tokens=2048
    )
    
    # Bind tools to model
    model_with_tools = model.bind_tools(tools)
    
    # System message for Resources Agent
    if verbose:
        system_msg = """You are a Kubernetes Resources Agent specializing in CPU/memory capacity and usage monitoring.

🚨 **FIRST CHECK THIS PATTERN** 🚨
BEFORE doing ANYTHING else, check if the user's question contains:
  - Words: "highest" OR "most" OR "largest" 
  - AND words: "memory" OR "mem"
  - AND words: "pod" OR "pods"

IF YES → STOP! Call get_pod_memory_comparison() tool IMMEDIATELY. Do NOT read further instructions until you call this tool.

IF NO → Continue reading below.

🚨 **SECOND CHECK: IS THIS A POD QUESTION?** 🚨
If user's question contains "pod" OR "pods" OR "containers" OR "all namespaces":
  This is a POD-LEVEL question. Go directly to POD RESOURCE ROUTING in the TOOL SELECTION GUIDE.
  DO NOT call get_node_limits() or get_node_resources() for pod questions.
  
  Quick pod routing:
  - Question has "pod"/"pods" AND one specific field (cpu limit / memory limit / cpu request / memory request) → get_pod_specific_resource(field=...)
  - Question has "pod"/"pods" AND asks for ALL fields (limits AND requests together) → get_pod_resources(namespace='all')

IF NOT a pod question → Continue reading below.

🚨 **KEYWORD DETECTION: "LIMITS" (NODE questions only)** 🚨
If user's question contains "limit" or "limits" or "CPU limit" or "memory limit"
AND question does NOT mention "pod" or "pods":
  → **MANDATORY: USE get_node_limits() tool FIRST**
  → This tool extracts ONLY the Limits column (rightmost column)
  → Returns CPU Limits and Memory Limits directly - no table parsing needed
  → DO NOT call get_node_utilization() or get_node_resources() for limits queries
  
  Examples:
  - "what are CPU and memory limits on the master?" → get_node_limits(node_name="k8s-master-01")
  - "show me limits" → get_node_limits(node_name="all")
  - "CPU limit for worker" → get_node_limits(node_name="k8s-worker-01")

YOUR RESPONSIBILITY:
Monitor and report on resource allocation, capacity, limits, requests, and utilization.
You handle HOW MUCH resources (CPU/memory/storage) are available, requested, and used.

DISK/STORAGE QUESTIONS:
- If the user asks about disk/storage usage (including "current disk usage"), you MUST answer using allocation/limits/requests/allocatable from kubectl tools.
- Explicitly state that real-time pod disk usage is not available via metrics-server and you are reporting configured allocations/limits instead.
- For disk/storage questions, call get_node_resources() FIRST and report any storage/ephemeral-storage capacity/allocatable from node describe output.
- For disk/storage questions, ONLY report storage/ephemeral-storage capacity, allocatable, and allocated requests/limits. Do NOT mention CPU or memory.
- If ephemeral-storage requests/limits are not present, explicitly say "No ephemeral-storage requests/limits configured".
- Preserve storage units exactly as shown in output (Ki/Mi/Gi). Do NOT drop units.

CLUSTER CONTEXT - NODE NAMES:
This cluster has 2 nodes with the following ACTUAL names in Kubernetes:
1. Master node: k8s-master-01.us-west1-a.c.project-f972fc71-9c5d-48d5-99f.internal (short name: k8s-master-01)
   - User may refer to it as: "master", "master node", "k8s-master", "k8s master", "the master", etc.
   - ALWAYS use "k8s-master-01" when referencing this node

2. Worker node: k8s-worker-01 (full name: k8s-worker-01)
   - User may refer to it as: "worker", "worker node", "k8s-worker", "k8s worker", "the worker", etc.
   - ALWAYS use "k8s-worker-01" when referencing this node

IMPORTANT: When user says "worker" or "master" (in any variation), understand they mean k8s-worker-01 or k8s-master-01 respectively.

AVAILABLE TOOLS (5 TOOLS):

1. get_node_resources()
   - Node capacity and allocatable resources
   - Shows total vs allocatable CPU/memory/storage
   - **CRITICAL: Output contains "Allocated resources" table with TWO columns: "Requests" and "Limits"**
   - Use for: "How much CPU/memory does each node have?", "What is capacity?"

2. get_node_limits(node_name='all')
   - **USE THIS FOR "LIMITS" QUERIES** - Extracts ONLY the Limits column values
   - Returns CPU Limits and Memory Limits directly (no table parsing needed)
   - Specifically targets the rightmost column from Allocated resources
   - Use for: "What are the limits?", "Show me limits", "CPU and memory limits", "limits on master"

3. get_pod_specific_resource(field, namespace='default')
   - **USE WHEN user asks about ONE specific field only**
   - field must be one of: cpu_limits, memory_limits, cpu_requests, memory_requests
   - Extracts ONLY that one field in Python — never mixes other fields
   - Returns pre-formatted text: "pod-name: value or not set" per line
   - Use for: "What are the CPU limits?", "Show me memory limits", "CPU requests for pods?",
              "Memory requests?", "Which pods have no CPU limits?"
   - DECISION RULE: question mentions ONE of (cpu limit / memory limit / cpu request / memory request) → this tool

4. get_pod_resources(namespace='all')
   - **USE WHEN user asks for ALL fields together in one answer**
   - Returns a pre-formatted table with ALL 4 fields per pod: CPU Limit, Mem Limit, CPU Request, Mem Request
   - Output is already formatted — do NOT try to parse JSON, just present the table as-is
   - Use for: "Show me all resource limits and requests",
              "Give me full resource config for all pods",
              "Show both limits and requests for all pods"
   - DECISION RULE: question explicitly asks for BOTH limits AND requests, or ALL resource info → this tool

4. get_namespace_resources()
   - Aggregate resources by namespace
   - Total requests/limits per namespace
   - Use for: "Which namespace uses most resources?"

5. get_pod_memory_comparison(namespace='all')
   - **CRITICAL TOOL** - Automatically compares CPU AND memory across ALL pods
   - Parses JSON, calculates totals, sorts by CPU/memory, returns highest
   - **USE THIS FIRST for any "highest/most CPU or memory" query**
   - Returns pre-formatted output with sorted pods and winners for both CPU and memory
   - Works WITHOUT metrics-server (uses resource requests/limits)

TOOL SELECTION GUIDE:

# ─── STEP 1: CHECK IF QUESTION IS ABOUT PODS ──────────────────────────────────
# Keywords: "pods", "pod", "all namespaces", "containers"
# If question mentions pods or asks for pod-level data → go to POD ROUTING below
# NEVER call get_node_limits or get_node_resources for pod questions

# ─── POD RESOURCE ROUTING ─────────────────────────────────────────────────────
# RULE: Does the question name ONE specific field (cpu limit OR memory limit OR cpu request OR memory request)?
#   YES, one field only → get_pod_specific_resource(field=...)
#   NO, asks for multiple fields or ALL → get_pod_resources()

"What are the CPU limits for pods?"                              → get_pod_specific_resource(field='cpu_limits')
"What are the memory limits for pods?"                           → get_pod_specific_resource(field='memory_limits')
"What are the CPU requests for pods?"                            → get_pod_specific_resource(field='cpu_requests')
"What are the memory requests for pods?"                         → get_pod_specific_resource(field='memory_requests')
"Which pods have no CPU limits?"                                 → get_pod_specific_resource(field='cpu_limits')
"Show me memory limits in kube-system"                           → get_pod_specific_resource(field='memory_limits', namespace='kube-system')

"Show me all cpu and memory limits and requests for all pods"    → get_pod_resources(namespace='all')
"Show me all resource limits and requests"                       → get_pod_resources()
"Give me full resource config for all pods"                      → get_pod_resources()
"Show both CPU and memory limits AND requests"                   → get_pod_resources()
"What are resource limits and requests on all pods?"             → get_pod_resources(namespace='all')
"All resource info for pods"                                     → get_pod_resources()
# ──────────────────────────────────────────────────────────────────────────────

# ─── STEP 2: NODE QUESTIONS (only when "node", "master", or "worker" mentioned) ──
"How much CPU/memory on nodes?" → get_node_resources()
"What is node capacity?" → get_node_resources()

**"What are the limits on nodes?" → get_node_limits()**
**"Show me limits on master" → get_node_limits(node_name="k8s-master-01")**
**"CPU and memory limits on master" → get_node_limits(node_name="k8s-master-01")**
**"Limits on master" → get_node_limits(node_name="k8s-master-01")**
**"Memory limit for worker" → get_node_limits(node_name="k8s-worker-01")**

"Which namespace uses most?" → get_namespace_resources()

**HIGHEST/MOST CPU OR MEMORY QUERIES - ALWAYS USE get_pod_memory_comparison():**
"Which pod has highest CPU?" → get_pod_memory_comparison()
"Find pod with most CPU" → get_pod_memory_comparison()
"Pod with largest CPU allocation" → get_pod_memory_comparison()
"Which pod uses most CPU?" → get_pod_memory_comparison()
"Which pod has highest memory?" → get_pod_memory_comparison()
"Find pod with most memory" → get_pod_memory_comparison()
"Pod with largest memory allocation" → get_pod_memory_comparison()
"Which pod uses most memory?" → get_pod_memory_comparison()
"Find pod with highest memory usage" → get_pod_memory_comparison()
"Highest memory pod" → get_pod_memory_comparison()
"...and find pod with highest memory..." → get_pod_memory_comparison()
"...pod with.*memory.*highest..." → get_pod_memory_comparison()

**CRITICAL PATTERN MATCHING RULE:** 
If the user's question contains ANY of these words together:
  - ("pod" OR "pods") AND ("highest" OR "most" OR "largest") AND "memory"
  
Then you MUST:
1. IMMEDIATELY call get_pod_memory_comparison() tool AS YOUR FIRST ACTION
2. DO NOT call get_pod_utilization() or get_node_resources() first
3. DO NOT say "metrics-server unavailable" - this tool works without it
4. IGNORE other parts of the question temporarily - focus on memory comparison first
5. After getting the result, THEN you can address other parts of the question

Example: User asks "check pods and find highest memory and check health"
  → You see "find highest memory" → IMMEDIATELY call get_pod_memory_comparison()
  → Report the result: "Pod X has highest memory with Y Mi"
  → Then address other parts if needed
2. DO NOT call get_pod_utilization() or get_pod_resources()
3. The get_pod_memory_comparison() tool does everything - parsing, comparing, finding winner
4. Just report what the tool returns
5. NEVER say "metrics-server unavailable" without calling get_pod_memory_comparison() first

RESPONSE RULES:
- **⚠️ #1 RULE - ANSWER ONLY WHAT WAS ASKED. NOTHING MORE.**
  Before writing your answer, identify the EXACT metric asked:
  - Question has "memory limit"  → write ONLY memory limits. STOP. Do not add CPU or requests.
  - Question has "CPU limit"     → write ONLY CPU limits. STOP. Do not add memory or requests.
  - Question has "memory request"→ write ONLY memory requests. STOP.
  - Question has "CPU request"   → write ONLY CPU requests. STOP.
  - Question has "limit" (no CPU/memory prefix) → write CPU Limits AND Memory Limits. STOP.
  - Question has "request" (no prefix) → write CPU Requests AND Memory Requests. STOP.

  FORBIDDEN: Do NOT include any field not explicitly asked for.
  FORBIDDEN: Do NOT add storage, disk, or "not available" sections if not asked.
  FORBIDDEN: Do NOT say "here are the resource limits AND requests" when only limits were asked.

  TEMPLATE FOR "memory limits" questions:
  Memory Limits:
  - <pod-name>: <value or "not set">
  - <pod-name>: <value or "not set">
  [END - write nothing else]

  TEMPLATE FOR "cpu limits" questions:
  CPU Limits:
  - <pod-name>: <value or "not set">
  - <pod-name>: <value or "not set">
  [END - write nothing else]

  TEMPLATE FOR "cpu requests" questions:
  CPU Requests:
  - <pod-name>: <value or "not set">
  [END]

  TEMPLATE FOR "memory requests" questions:
  Memory Requests:
  - <pod-name>: <value or "not set">
  [END]

  CRITICAL LIST RULES (applies to all templates above):
  - List EVERY pod by name. Do NOT summarize or group them.
  - Do NOT write "Most pods have no limit set" — list each pod individually.
  - Do NOT add any explanation after the list (e.g. "CPU limits are the maximum...").
  - If a pod has no value, write "not set" next to its name.

- **⚠️ If user's question contains "limit" or "limits": report the Limits COLUMN (rightmost), NOT Requests.**
- For capacity queries → Use get_node_resources
- For utilization queries → Use get_node_utilization or get_pod_utilization
- For limits/requests → Use get_pod_resources or get_namespace_resources
- If asked about HEALTH status → say "Health Agent handles that"
- If asked about WHAT EXISTS (listing/counting) → say "Describe Agent handles that"
- **CRITICAL: NEVER return raw JSON or kubectl output. Always summarize in plain English**
- **CRITICAL: If tool output says "METRICS-SERVER NOT AVAILABLE", you MUST clearly state you're showing ALLOCATED/RESERVED resources, NOT real-time usage**
- Present numbers clearly (CPU in cores/millicores, memory in Mi/Gi)
- When metrics-server is unavailable, say "allocated" or "reserved" NOT "using" or "consuming"

METRICS-SERVER NOTE:
- kubectl top commands require metrics-server
- If not installed, explain error and suggest using resource requests/limits instead

HOW TO PARSE LIMITS FROM get_node_resources() OUTPUT:

The output contains this table:

Allocated resources:
  Resource           Requests    Limits
  --------           --------    ------
  cpu                950m (47%)  0 (0%)
  memory             290Mi (7%)  340Mi (8%)

CRITICAL PARSING RULES:
1. "Requests" = MIDDLE column (950m, 290Mi)
2. "Limits" = RIGHT column (0, 340Mi)
3. When user asks for "limits" → Report the RIGHT column values
4. When user asks for "requests" → Report the MIDDLE column values

SIMPLE RULE: 
- Question has "limit"? → Answer with numbers from Limits column (right side)
- Question has "request"? → Answer with numbers from Requests column (middle)
- Question has both or neither? → Show both, but emphasize what they asked for

Example responses:
Q: "what are CPU and memory limits on master?"
A: "CPU Limits: 0 (0%) - no limit configured. Memory Limits: 340Mi (8%)."

Q: "what are limits on master?"
A: "Limits: CPU 0 (unlimited), Memory 340Mi (8%)"

Q: "show me requests and limits"
A: "CPU - Requests: 950m (47%), Limits: 0 (0%). Memory - Requests: 290Mi (7%), Limits: 340Mi (8%)"

EXAMPLES:

User: "How much CPU does each node have?"
→ get_node_resources()
→ Present total and allocatable CPU

User: "What are CPU and memory limits on the master?"
→ get_node_resources()
→ Find "Allocated resources" table in output
→ Look at the "Limits" column (rightmost column with numbers)
→ Report: "CPU Limits: 0 (0%) - meaning no limit set"
           "Memory Limits: 340Mi (8%)"
→ Optionally add: "For reference, Requests are: CPU 950m (47%), Memory 290Mi (7%)"

User: "What are the limits on master?"
→ Same as above - focus on Limits column values first

User: "What is current node utilization?"
→ get_node_utilization()
→ Show CPU/memory usage percentages

User: "Which pods use most memory?"
→ get_pod_utilization('all')
→ Sort by memory usage and show top consumers

Always use tools, never guess resource values."""
    else:
        system_msg = """You are a Kubernetes Resources Agent. Monitor resource capacity, allocation, and usage.

🚨 CHECK ORDER — follow strictly:

1. Question has "highest/most/largest" + "memory/cpu" + "pod"?
   → call get_pod_memory_comparison() IMMEDIATELY

2. Question mentions "pod" OR "pods" OR "all namespaces"?
   → POD QUESTION — use pod tools below. NEVER call get_node_limits or get_node_resources.
   - ONE field asked (cpu limit / memory limit / cpu request / memory request) → get_pod_specific_resource(field=...)
     field values: cpu_limits, memory_limits, cpu_requests, memory_requests
   - ALL fields asked (limits AND requests together) → get_pod_resources(namespace='all')

3. Question mentions "node" OR "master" OR "worker" AND has "limit"?
   → get_node_limits(node_name='all')

4. Node capacity questions → get_node_resources()
5. Namespace aggregate → get_namespace_resources()
6. Real-time node usage → get_node_utilization()
7. Real-time pod usage → get_pod_utilization()
8. Disk/storage → get_node_resources(), report storage/ephemeral-storage only

TOOLS:
- get_node_resources: Node capacity and allocatable resources
- get_node_limits(node_name): Extracts ONLY Limits column from node describe (for node limit questions)
- get_pod_specific_resource(field, namespace): ONE specific resource field per pod — never mixes fields
- get_pod_resources(namespace): Pre-formatted table with all 4 fields (cpu limit, mem limit, cpu req, mem req) per pod. Present output as-is, do NOT parse as JSON.
- get_namespace_resources: Aggregate CPU/memory by namespace
- get_node_utilization: Current node usage (needs metrics-server)
- get_pod_utilization: Current pod usage (needs metrics-server)
- get_pod_memory_comparison: Find pod with highest CPU or memory (works WITHOUT metrics-server)

RULES:
- Never guess resource values — always use tools
- Health queries → Health Agent
- Listing/counting → Describe Agent
- Present numbers clearly (millicores, Mi/Gi)"""
    
    # Create agent node
    def resources_agent_node(state):
        """Resources agent with system message"""
        from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage, AIMessage
        
        messages = state["messages"]

        def _filter_storage_lines(text: str) -> str:
            if not text:
                return text
            keep_keywords = [
                "name:",
                "capacity:",
                "allocatable:",
                "allocated resources:",
                "resource",
                "requests",
                "limits",
                "ephemeral-storage",
            ]
            lines = text.splitlines()
            kept = [line for line in lines if any(k in line.lower() for k in keep_keywords)]
            # If nothing matched, fall back to original text
            return "\n".join(kept) if kept else text

        # Extract most recent user question text
        user_question = ""
        for m in reversed(messages):
            if isinstance(m, HumanMessage):
                user_question = m.content if isinstance(m.content, str) else str(m.content)
                break
        
        # Check if we have tool results and need final answer
        has_tool_results = any(isinstance(m, ToolMessage) for m in messages)
        last_message = messages[-1]
        has_pending_tool_calls = hasattr(last_message, 'tool_calls') and last_message.tool_calls

        # Force tool call: namespace resource allocation (MUST be before disk check — supervisor
        # rewrites question to include "storage" which would incorrectly trigger disk detection)
        if _is_namespace_resources_question(user_question) and not has_tool_results and not has_pending_tool_calls:
            return {
                "messages": [
                    AIMessage(
                        content="Calling get_namespace_resources for per-namespace allocation.",
                        tool_calls=[{"name": "get_namespace_resources", "args": {}, "id": "force_namespace_resources"}]
                    )
                ]
            }

        # Force tool call for disk/storage questions to ensure node storage context
        if _is_disk_question(user_question) and not has_tool_results and not has_pending_tool_calls:
            return {
                "messages": [
                    AIMessage(
                        content="Calling get_node_resources for disk/storage context.",
                        tool_calls=[{"name": "get_node_resources", "args": {}, "id": "disk_node_resources"}]
                    )
                ]
            }

        # Force tool call: "which pods don't have limits/requests?" — needs full table to filter
        if _is_pods_without_limits_question(user_question) and not has_tool_results and not has_pending_tool_calls:
            ns = "all" if ("all namespace" in user_question.lower() or "all ns" in user_question.lower() or "across" in user_question.lower()) else "default"
            return {
                "messages": [
                    AIMessage(
                        content="Calling get_pod_resources to find pods missing limits.",
                        tool_calls=[{"name": "get_pod_resources", "args": {"namespace": ns}, "id": "force_pods_without_limits"}]
                    )
                ]
            }


        if _is_pod_comparison_question(user_question) and not has_tool_results and not has_pending_tool_calls:
            ns = "all" if ("all namespace" in user_question.lower() or "all ns" in user_question.lower() or "across" in user_question.lower()) else "default"
            return {
                "messages": [
                    AIMessage(
                        content="Calling get_pod_memory_comparison to find pod with highest resource usage.",
                        tool_calls=[{"name": "get_pod_memory_comparison", "args": {"namespace": ns}, "id": "force_pod_comparison"}]
                    )
                ]
            }

        # Force tool call: all pod resources (limits + requests together)
        if _is_all_pod_resources_question(user_question) and not has_tool_results and not has_pending_tool_calls:
            ns = "all" if ("all namespace" in user_question.lower() or "all ns" in user_question.lower() or "across" in user_question.lower()) else "default"
            return {
                "messages": [
                    AIMessage(
                        content=f"Calling get_pod_resources for all resource fields.",
                        tool_calls=[{"name": "get_pod_resources", "args": {"namespace": ns}, "id": "force_pod_resources"}]
                    )
                ]
            }

        # Force tool call: single specific pod field
        single_field = _is_single_field_pod_question(user_question)
        if single_field and not has_tool_results and not has_pending_tool_calls:
            field, ns = single_field
            return {
                "messages": [
                    AIMessage(
                        content=f"Calling get_pod_specific_resource for {field}.",
                        tool_calls=[{"name": "get_pod_specific_resource", "args": {"field": field, "namespace": ns}, "id": "force_pod_specific"}]
                    )
                ]
            }
        
        if has_tool_results and not has_pending_tool_calls:
            if _is_disk_question(user_question) and not _is_namespace_resources_question(user_question):
                filtered_messages = []
                for m in messages:
                    if isinstance(m, ToolMessage):
                        filtered_messages.append(
                            ToolMessage(
                                content=_filter_storage_lines(str(m.content)),
                                tool_call_id=m.tool_call_id
                            )
                        )
                    else:
                        filtered_messages.append(m)
                messages = filtered_messages

            # For "which pods don't have limits?" — filter table to missing-only rows
            if _is_pods_without_limits_question(user_question):
                tool_output = next(
                    (str(m.content) for m in messages if isinstance(m, ToolMessage)),
                    None
                )
                if tool_output:
                    return {"messages": [AIMessage(content=_extract_pods_without_limits(tool_output))]}

            # For namespace allocation — return table directly
            if _is_namespace_resources_question(user_question):
                tool_output = next(
                    (str(m.content) for m in messages if isinstance(m, ToolMessage)),
                    None
                )
                if tool_output:
                    return {"messages": [AIMessage(content=tool_output)]}

            # For pod table/single-field queries: return tool output directly, skip LLM
            single = _is_single_field_pod_question(user_question)
            if _is_all_pod_resources_question(user_question) or single:
                tool_output = next(
                    (str(m.content) for m in messages if isinstance(m, ToolMessage)),
                    None
                )
                if tool_output:
                    # If user asked for a total, append the summed value
                    if single and _is_total_resource_question(user_question):
                        field, _ = single
                        tool_output = _append_total(tool_output, field)
                    return {"messages": [AIMessage(content=tool_output)]}

            # For all other queries: LLM summarizes
            messages_with_system = [SystemMessage(content=system_msg)] + messages + [
                HumanMessage(content="""Now provide a clear, concise summary of the resource information.

CRITICAL INSTRUCTIONS:
- NO raw JSON - only human-readable text with specific numbers
- If the tool output contains '⚠️ METRICS-SERVER NOT AVAILABLE', you MUST explicitly state this is ALLOCATED/RESERVED resources, NOT actual real-time usage
- If the user asked about disk/storage usage, explicitly state real-time pod disk usage isn't available and you are reporting configured allocation/limits/allocatable values instead
- If the user asked about disk/storage usage, only include storage/ephemeral-storage details (capacity, allocatable, requests/limits). Exclude CPU/memory details
- Preserve storage units (Ki/Mi/Gi) exactly as shown in tool output
- Use words like "allocated", "reserved", "requested" - NEVER say "using", "consuming", or "current usage"
- Example: "Master node has 950m CPU ALLOCATED (47% of requests)" NOT "Master node is using 950m CPU"
- DO NOT mention pod counts or say "X pods running" - focus ONLY on CPU/memory/storage numbers
- DO NOT say things like "8 pods" or "total pods" - that information belongs to a different agent""")
            ]
            response = model_with_tools.invoke(messages_with_system)
        else:
            # Normal flow
            if not any(isinstance(m, SystemMessage) for m in messages):
                messages = [SystemMessage(content=system_msg)] + messages
            
            response = model_with_tools.invoke(messages)
        
        return {"messages": [response]}
    
    # Create tool node with async support for MCP tools
    def tool_node(state):
        """Execute MCP tools (async) and return results"""
        from langchain_core.messages import ToolMessage
        import asyncio
        
        messages = state["messages"]
        last_message = messages[-1]
        
        async def execute_tools_async():
            tool_results = []
            
            if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
                for tool_call in last_message.tool_calls:
                    tool_name = tool_call["name"]
                    tool_args = tool_call.get("args", {})
                    
                    # Find and execute the MCP tool
                    tool_found = False
                    for tool in tools:
                        if tool.name == tool_name:
                            tool_found = True
                            try:
                                # MCP tools require async invocation
                                result = await tool.ainvoke(tool_args)
                                tool_results.append(
                                    ToolMessage(
                                        content=str(result),
                                        tool_call_id=tool_call["id"]
                                    )
                                )
                            except Exception as e:
                                tool_results.append(
                                    ToolMessage(
                                        content=f"Error executing {tool_name}: {str(e)}",
                                        tool_call_id=tool_call["id"]
                                    )
                                )
                            break
                    
                    if not tool_found:
                        tool_results.append(
                            ToolMessage(
                                content=f"Tool '{tool_name}' not found",
                                tool_call_id=tool_call["id"]
                            )
                        )
            
            return tool_results
        
        # Run async execution
        tool_results = asyncio.run(execute_tools_async())
        return {"messages": tool_results}
    
    # Build workflow
    workflow = StateGraph(MessagesState)
    
    # Add nodes
    workflow.add_node("resources_agent", resources_agent_node)
    workflow.add_node("tools", tool_node)
    
    # Set entry point
    workflow.set_entry_point("resources_agent")
    
    # Add conditional edges
    def should_continue(state):
        messages = state["messages"]
        last_message = messages[-1]
        
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            # Count tool calls to prevent infinite loops
            tool_call_count = sum(1 for m in messages if hasattr(m, 'tool_calls') and m.tool_calls)
            if tool_call_count > 3:
                return "__end__"
            return "tools"
        return "__end__"
    
    workflow.add_conditional_edges(
        "resources_agent",
        should_continue,
        {"tools": "tools", "__end__": "__end__"}
    )
    
    workflow.add_edge("tools", "resources_agent")
    
    return workflow


# ============================================================================
# RESPONSE POST-PROCESSOR - Filter LLM output to only what was asked
# ============================================================================

def _filter_resource_response(question: str, answer: str) -> str:
    """
    Post-process LLM answer to remove fields the user did NOT ask for.
    Haiku cannot reliably filter itself, so we do it in Python.
    """
    q = question.lower()

    # Determine which fields were explicitly requested
    asked_memory_limit   = "memory limit" in q or "memory limits" in q
    asked_cpu_limit      = "cpu limit" in q or "cpu limits" in q
    asked_memory_request = "memory request" in q or "memory requests" in q
    asked_cpu_request    = "cpu request" in q or "cpu requests" in q
    asked_limits_only    = ("limit" in q or "limits" in q) and "request" not in q and "memory" not in q and "cpu" not in q
    asked_requests_only  = ("request" in q or "requests" in q) and "limit" not in q and "memory" not in q and "cpu" not in q
    asked_generic        = "resource" in q and "limit" not in q and "request" not in q

    # If question is generic → return full answer unchanged
    if asked_generic or (not any([asked_memory_limit, asked_cpu_limit,
                                   asked_memory_request, asked_cpu_request,
                                   asked_limits_only, asked_requests_only])):
        return answer

    # Define keep vs remove patterns
    keep_patterns   = []
    remove_patterns = []

    if asked_memory_limit:
        # Broad keep: any line mentioning "memory" is relevant — haiku mixes fields in one sentence
        keep_patterns   = ["memory"]
        # Remove lines that mention ONLY cpu/storage with zero memory mention
        remove_patterns = ["storage", "disk", "real-time", "ephemeral",
                           "not available", "not reported"]
    elif asked_cpu_limit:
        # Broad keep: any line mentioning "cpu" is relevant
        keep_patterns   = ["cpu"]
        # Remove lines that mention ONLY memory/storage with zero cpu mention
        remove_patterns = ["storage", "disk", "real-time", "ephemeral",
                           "not available", "not reported"]
    elif asked_memory_request:
        keep_patterns   = ["memory"]
        remove_patterns = ["storage", "disk", "real-time", "ephemeral",
                           "not available", "not reported"]
    elif asked_cpu_request:
        keep_patterns   = ["cpu"]
        remove_patterns = ["storage", "disk", "real-time", "ephemeral",
                           "not available", "not reported"]
    elif asked_limits_only:
        keep_patterns   = ["limit"]
        remove_patterns = ["request", "storage", "disk", "real-time", "ephemeral",
                           "not available", "not reported"]
    elif asked_requests_only:
        keep_patterns   = ["request"]
        remove_patterns = ["limit", "storage", "disk", "real-time", "ephemeral",
                           "not available", "not reported"]

    if not remove_patterns:
        return answer

    # Section-level skip triggers — entire paragraph/section after these is dropped
    # These are phrases that, when found in a line, signal the start of an unwanted section
    # including the header line itself
    _requests_section_triggers = [
        "cpu request", "cpu requests", "memory request", "memory requests",
        "are requesting", "requesting the following", "following resource requests",
        "resource requests", "pods are requesting",
    ]
    _storage_section_triggers = [
        "real-time", "storage/ephemeral", "configured storage",
        "disk usage", "ephemeral-storage",
    ]

    if asked_memory_limit or asked_cpu_limit:
        section_skip_triggers = _requests_section_triggers + _storage_section_triggers
    else:
        section_skip_triggers = _storage_section_triggers

    filtered_lines = []
    skip_section   = False

    lines = answer.split("\n")
    i = 0
    while i < len(lines):
        line       = lines[i]
        line_lower = line.lower().strip()

        # Detect start of an unwanted section
        if any(p in line_lower for p in section_skip_triggers):
            skip_section = True

        if skip_section:
            # Resume only at a blank line followed by a non-bullet, non-indented line
            # that doesn't contain remove patterns
            is_blank = line.strip() == ""
            if is_blank:
                # peek ahead for next non-blank
                j = i + 1
                while j < len(lines) and lines[j].strip() == "":
                    j += 1
                if j < len(lines):
                    next_line = lines[j].lower().strip()
                    if not any(p in next_line for p in remove_patterns + section_skip_triggers):
                        skip_section = False
            i += 1
            continue

        # Drop any line (bullet OR prose) that exclusively talks about removed fields
        has_remove = any(p in line_lower for p in remove_patterns)
        has_keep   = any(p in line_lower for p in keep_patterns)

        if has_remove and not has_keep:
            i += 1
            continue

        filtered_lines.append(line)
        i += 1

    result = "\n".join(filtered_lines).strip()
    import re
    result = re.sub(r'\n{3,}', '\n\n', result)
    return result if result else answer


# ============================================================================
# AGENT INVOCATION FUNCTION
# ============================================================================

def ask_resources_agent(question: str, api_key: str = None, verbose: bool = False) -> dict:
    """
    Ask the Resources Agent a question and get a response.
    Uses workflow caching for performance.
    
    Args:
        question: User's question about resources
        api_key: Anthropic API key (optional)
        verbose: Whether to show detailed reasoning
    
    Returns:
        Dict with 'answer' and 'messages'
    """
    global _cached_workflow, _cached_api_key
    
    # Get API key
    anthropic_api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
    if not anthropic_api_key:
        return {
            'answer': "Error: Anthropic API key required. Set ANTHROPIC_API_KEY environment variable.",
            'messages': []
        }
    
    # FORCE WORKFLOW RECREATION - Don't use cache for now to ensure new tool is loaded
    _cached_workflow = None
    _cached_api_key = None
    
    # Check if we need to recreate workflow (API key changed or first run)
    if _cached_workflow is None or _cached_api_key != anthropic_api_key:
        _cached_workflow = create_resources_agent(api_key=anthropic_api_key, verbose=verbose).compile()
        _cached_api_key = anthropic_api_key
    
    try:
        from langchain_core.messages import HumanMessage
        
        # Invoke the workflow
        result = _cached_workflow.invoke({
            "messages": [HumanMessage(content=question)]
        })
        
        # Extract the final answer from last AIMessage
        # Look backwards through messages to find the last AIMessage with actual text content
        answer = "No response generated"
        for msg in reversed(result["messages"]):
            if hasattr(msg, 'content'):
                if isinstance(msg.content, str) and msg.content.strip():
                    answer = msg.content
                    break
                elif isinstance(msg.content, list):
                    # Extract text from content blocks
                    text_parts = [
                        block.get('text', '') if isinstance(block, dict) else str(block)
                        for block in msg.content
                        if isinstance(block, dict) and block.get('type') == 'text'
                    ]
                    if text_parts:
                        answer = " ".join(text_parts)
                        break

        # Post-process: filter answer to only fields the user asked for
        # Skip filtering for pod table/single-field/total queries — output is already exact
        if not _is_all_pod_resources_question(question) and not _is_single_field_pod_question(question) and not _is_pods_without_limits_question(question) and not _is_namespace_resources_question(question):
            answer = _filter_resource_response(question, answer)

        return {
            'answer': answer,
            'messages': result["messages"]
        }
        
    except Exception as e:
        return {
            'answer': f"Resources Agent error: {str(e)}",
            'messages': []
        }
