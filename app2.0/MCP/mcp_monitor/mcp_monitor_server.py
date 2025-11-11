"""
MCP Server for Monitor Agent Tools
Exposes Prometheus monitoring tools via MCP protocol
"""

import os
import requests
from typing import Optional
from mcp.server.fastmcp import FastMCP

# Get port from environment or default to 8004
port = int(os.getenv('PORT', '8004'))

# Initialize MCP server with explicit port
mcp = FastMCP("K8s-Monitor", port=port)

# Prometheus configuration
PROMETHEUS_URL = os.getenv('PROMETHEUS_URL', 'http://34.59.188.124:9090')
PROMETHEUS_TIMEOUT = 10


@mcp.tool()
def query_prometheus_instant(query: str, time: str = "") -> str:
    """
    Execute instant Prometheus query at a single point in time.
    
    Args:
        query: PromQL query expression
        time: Optional timestamp (default: now)
    
    Returns:
        Formatted string with metric values
    """
    try:
        params = {"query": query}
        if time:
            params["time"] = time
        
        response = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query",
            params=params,
            timeout=PROMETHEUS_TIMEOUT
        )
        response.raise_for_status()
        
        result = response.json()
        
        if result.get('status') != 'success':
            return f"Query failed: {result.get('error', 'Unknown error')}"
        
        data = result.get('data', {})
        results = data.get('result', [])
        
        if not results:
            return f"No data returned for query: {query}"
        
        output = f"Query: {query}\nResults:\n" + "-" * 80 + "\n"
        
        for item in results:
            metric = item.get('metric', {})
            value = item.get('value', [None, None])
            
            labels = ", ".join([f"{k}='{v}'" for k, v in metric.items()])
            metric_str = f"{{{labels}}}" if labels else "{}"
            
            output += f"Metric: {metric_str}\nValue: {value[1]}\n\n"
        
        return output
        
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool()
def query_prometheus_range(query: str, start: str, end: str, step: str = "1m") -> str:
    """
    Execute Prometheus range query over time period.
    
    Args:
        query: PromQL query expression
        start: Start time - Unix timestamp or relative like "1h" for 1 hour ago
        end: End time - Unix timestamp or "now"
        step: Query resolution (default: "1m")
    
    Returns:
        Formatted string with time-series data
    """
    try:
        import time
        
        # Convert relative times to Unix timestamps
        def parse_time(time_str):
            if time_str == "now":
                return int(time.time())
            elif time_str.endswith('h'):
                hours = int(time_str[:-1])
                return int(time.time() - hours * 3600)
            elif time_str.endswith('m'):
                minutes = int(time_str[:-1])
                return int(time.time() - minutes * 60)
            elif time_str.endswith('d'):
                days = int(time_str[:-1])
                return int(time.time() - days * 86400)
            else:
                # Assume it's already a timestamp
                return time_str
        
        start_ts = parse_time(start)
        end_ts = parse_time(end)
        
        params = {"query": query, "start": start_ts, "end": end_ts, "step": step}
        
        response = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query_range",
            params=params,
            timeout=PROMETHEUS_TIMEOUT * 2
        )
        response.raise_for_status()
        
        result = response.json()
        
        if result.get('status') != 'success':
            return f"Query failed: {result.get('error', 'Unknown error')}"
        
        data = result.get('data', {})
        results = data.get('result', [])
        
        if not results:
            return f"No data returned for query: {query}"
        
        output = f"Query: {query}\nTime Range: {start} to {end}\nSeries: {len(results)}\n\n"
        
        for idx, item in enumerate(results[:5]):
            metric = item.get('metric', {})
            values = item.get('values', [])
            
            labels = ", ".join([f"{k}='{v}'" for k, v in metric.items()])
            output += f"Series {idx + 1}: {{{labels}}}\n"
            output += f"Data Points: {len(values)}\n"
            
            if values:
                output += f"  First: {values[0][1]}\n"
                output += f"  Last: {values[-1][1]}\n\n"
        
        if len(results) > 5:
            output += f"... and {len(results) - 5} more series\n"
        
        return output
        
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool()
def get_node_metrics(node_name: str = "", metric_type: str = "all") -> str:
    """
    Get node metrics from Prometheus.
    
    Args:
        node_name: Node name - can be hostname (k8s-master, k8s-worker) or IP:port (10.128.0.6:9100). Empty for all nodes.
        metric_type: "cpu", "memory", "disk", "network", or "all"
    
    Returns:
        Formatted node metrics including usage percentages and total capacities
    """
    try:
        output = "Node Metrics\n" + "=" * 80 + "\n"
        
        # Determine if node_name is a job name or instance
        # If it contains ":" it's likely an instance (IP:port), otherwise treat as job name
        label_selector = ""
        if node_name:
            if ":" in node_name:
                label_selector = f"instance='{node_name}'"
            else:
                label_selector = f"job='{node_name}'"
        
        # CPU
        if metric_type in ["cpu", "all"]:
            # Get CPU usage percentage
            if node_name:
                cpu_query = f"100 - (avg(rate(node_cpu_seconds_total{{{label_selector}, mode='idle'}}[5m])) * 100)"
            else:
                cpu_query = "100 - (avg by(job, instance) (rate(node_cpu_seconds_total{mode='idle'}[5m])) * 100)"
            
            resp = requests.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": cpu_query}, timeout=PROMETHEUS_TIMEOUT)
            if resp.status_code == 200:
                result = resp.json()
                if result.get('status') == 'success':
                    results = result.get('data', {}).get('result', [])
                    output += "CPU Usage:\n" + "-" * 80 + "\n"
                    for item in results:
                        job = item.get('metric', {}).get('job', '')
                        instance = item.get('metric', {}).get('instance', 'unknown')
                        display_name = f"{job} ({instance})" if job else instance
                        value = item.get('value', [None, None])[1]
                        output += f"  {display_name}: {float(value):.2f}%\n"
            
            # Get total CPU cores
            if node_name:
                cpu_cores_query = f"count(node_cpu_seconds_total{{{label_selector}, mode='idle'}})"
            else:
                cpu_cores_query = "count(node_cpu_seconds_total{mode='idle'}) by (job, instance)"
            
            resp = requests.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": cpu_cores_query}, timeout=PROMETHEUS_TIMEOUT)
            if resp.status_code == 200:
                result = resp.json()
                if result.get('status') == 'success':
                    results = result.get('data', {}).get('result', [])
                    output += "\nTotal CPU Cores:\n" + "-" * 80 + "\n"
                    for item in results:
                        job = item.get('metric', {}).get('job', '')
                        instance = item.get('metric', {}).get('instance', 'unknown')
                        display_name = f"{job} ({instance})" if job else instance
                        value = int(float(item.get('value', [None, None])[1]))
                        output += f"  {display_name}: {value} cores\n"
                    output += "\n"
        
        # Memory
        if metric_type in ["memory", "all"]:
            # Get memory usage percentage
            if node_name:
                mem_query = f"(node_memory_MemTotal_bytes{{{label_selector}}} - node_memory_MemAvailable_bytes{{{label_selector}}}) / node_memory_MemTotal_bytes{{{label_selector}}} * 100"
            else:
                mem_query = "(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes * 100"
            
            resp = requests.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": mem_query}, timeout=PROMETHEUS_TIMEOUT)
            if resp.status_code == 200:
                result = resp.json()
                if result.get('status') == 'success':
                    results = result.get('data', {}).get('result', [])
                    output += "Memory Usage:\n" + "-" * 80 + "\n"
                    for item in results:
                        job = item.get('metric', {}).get('job', '')
                        instance = item.get('metric', {}).get('instance', 'unknown')
                        display_name = f"{job} ({instance})" if job else instance
                        value = item.get('value', [None, None])[1]
                        output += f"  {display_name}: {float(value):.2f}%\n"
            
            # Get total memory capacity
            if node_name:
                mem_total_query = f"node_memory_MemTotal_bytes{{{label_selector}}}"
            else:
                mem_total_query = "node_memory_MemTotal_bytes"
            
            resp = requests.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": mem_total_query}, timeout=PROMETHEUS_TIMEOUT)
            if resp.status_code == 200:
                result = resp.json()
                if result.get('status') == 'success':
                    results = result.get('data', {}).get('result', [])
                    output += "\nTotal Memory Capacity:\n" + "-" * 80 + "\n"
                    for item in results:
                        job = item.get('metric', {}).get('job', '')
                        instance = item.get('metric', {}).get('instance', 'unknown')
                        display_name = f"{job} ({instance})" if job else instance
                        value_bytes = float(item.get('value', [None, None])[1])
                        value_gb = value_bytes / (1024**3)
                        output += f"  {display_name}: {value_gb:.2f} GB ({value_bytes:,.0f} bytes)\n"
                    output += "\n"
        
        return output
        
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool()
def get_pod_metrics(pod_name: str, namespace: str = "", metric_type: str = "all") -> str:
    """
    Get pod/container metrics from Prometheus.
    
    Args:
        pod_name: Pod name
        namespace: Kubernetes namespace (empty for all)
        metric_type: "cpu", "memory", "network", or "all"
    
    Returns:
        Formatted pod metrics
    """
    try:
        output = f"Pod Metrics: {pod_name}\n" + "=" * 80 + "\n"
        
        # CPU
        if metric_type in ["cpu", "all"]:
            cpu_query = f"rate(container_cpu_usage_seconds_total{{pod='{pod_name}'}}[5m]) * 100"
            if namespace:
                cpu_query = f"rate(container_cpu_usage_seconds_total{{pod='{pod_name}', namespace='{namespace}'}}[5m]) * 100"
            
            resp = requests.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": cpu_query}, timeout=PROMETHEUS_TIMEOUT)
            if resp.status_code == 200:
                result = resp.json()
                if result.get('status') == 'success':
                    results = result.get('data', {}).get('result', [])
                    if results:
                        output += "CPU Usage:\n" + "-" * 80 + "\n"
                        for item in results:
                            container = item.get('metric', {}).get('container', 'unknown')
                            value = item.get('value', [None, None])[1]
                            output += f"  {container}: {float(value):.4f}%\n"
                        output += "\n"
        
        # Memory
        if metric_type in ["memory", "all"]:
            mem_query = f"container_memory_usage_bytes{{pod='{pod_name}'}}"
            if namespace:
                mem_query = f"container_memory_usage_bytes{{pod='{pod_name}', namespace='{namespace}'}}"
            
            resp = requests.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": mem_query}, timeout=PROMETHEUS_TIMEOUT)
            if resp.status_code == 200:
                result = resp.json()
                if result.get('status') == 'success':
                    results = result.get('data', {}).get('result', [])
                    if results:
                        output += "Memory Usage:\n" + "-" * 80 + "\n"
                        for item in results:
                            container = item.get('metric', {}).get('container', 'unknown')
                            value = item.get('value', [None, None])[1]
                            mem_mb = float(value) / (1024 * 1024)
                            output += f"  {container}: {mem_mb:.2f} MB\n"
                        output += "\n"
        
        return output
        
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool()
def list_available_metrics(search: str = "") -> str:
    """
    List available metrics in Prometheus.
    
    Args:
        search: Optional search filter
    
    Returns:
        List of metric names
    """
    try:
        response = requests.get(f"{PROMETHEUS_URL}/api/v1/label/__name__/values", timeout=PROMETHEUS_TIMEOUT)
        response.raise_for_status()
        
        result = response.json()
        
        if result.get('status') != 'success':
            return f"Failed: {result.get('error', 'Unknown error')}"
        
        metrics = result.get('data', [])
        
        if search:
            metrics = [m for m in metrics if search.lower() in m.lower()]
        
        if not metrics:
            return "No metrics found"
        
        output = f"Available Metrics (Total: {len(metrics)})\n" + "=" * 80 + "\n"
        
        # Group by prefix
        grouped = {}
        for metric in metrics:
            prefix = metric.split('_')[0] if '_' in metric else 'other'
            if prefix not in grouped:
                grouped[prefix] = []
            grouped[prefix].append(metric)
        
        for prefix in sorted(grouped.keys()):
            output += f"\n{prefix.upper()} ({len(grouped[prefix])}):\n" + "-" * 80 + "\n"
            for metric in sorted(grouped[prefix])[:20]:
                output += f"  - {metric}\n"
            if len(grouped[prefix]) > 20:
                output += f"  ... and {len(grouped[prefix]) - 20} more\n"
        
        return output
        
    except Exception as e:
        return f"Error: {str(e)}"


if __name__ == "__main__":
    # Run server on HTTP transport
    # Port should be set via PORT environment variable when launching this script
    # Example: PORT=8004 python3 mcp_monitor_server.py
    mcp.run(transport="streamable-http")
