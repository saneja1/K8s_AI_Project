"""
Monitoring Tools for Prometheus Metrics
Tools for querying Prometheus API to get real-time and historical metrics
"""

import os
import requests
from typing import Optional
from langchain_core.tools import tool


# Prometheus configuration
PROMETHEUS_URL = os.getenv('PROMETHEUS_URL', 'http://34.53.50.194:9090')
PROMETHEUS_TIMEOUT = 10


@tool
def query_prometheus_instant(query: str, time: Optional[str] = None) -> str:
    """
    Execute instant Prometheus query at a single point in time.
    Returns current metric values from Prometheus.
    
    Args:
        query: PromQL query string. Common examples:
            - Node CPU usage: "100 - (avg by(instance) (rate(node_cpu_seconds_total{mode='idle'}[5m])) * 100)"
            - Node memory usage: "(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes * 100"
            - Node disk usage: "(node_filesystem_size_bytes{mountpoint='/'} - node_filesystem_avail_bytes{mountpoint='/'}) / node_filesystem_size_bytes{mountpoint='/'} * 100"
            - Pod CPU: "rate(container_cpu_usage_seconds_total{pod='pod-name'}[5m]) * 100"
            - Pod memory: "container_memory_usage_bytes{pod='pod-name'}"
            - All targets status: "up"
        time: Optional RFC3339 timestamp or Unix timestamp (default: now)
    
    Returns:
        JSON string with metric values from Prometheus
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
        
        # Format response for better readability
        data = result.get('data', {})
        result_type = data.get('resultType', '')
        results = data.get('result', [])
        
        if not results:
            return f"No data returned for query: {query}"
        
        # Format output
        output = f"Query: {query}\n"
        output += f"Result Type: {result_type}\n"
        output += f"Timestamp: {results[0].get('value', [''])[0] if results else 'N/A'}\n\n"
        output += "Results:\n"
        output += "-" * 80 + "\n"
        
        for item in results:
            metric = item.get('metric', {})
            value = item.get('value', [None, None])
            
            # Format metric labels
            labels = ", ".join([f"{k}='{v}'" for k, v in metric.items()])
            metric_str = f"{{{labels}}}" if labels else "{}"
            
            output += f"Metric: {metric_str}\n"
            output += f"Value: {value[1]}\n\n"
        
        return output
        
    except requests.exceptions.RequestException as e:
        return f"Error connecting to Prometheus at {PROMETHEUS_URL}: {str(e)}"
    except Exception as e:
        return f"Error executing query: {str(e)}"


@tool
def query_prometheus_range(query: str, start: str, end: str, step: str = "1m") -> str:
    """
    Execute Prometheus range query over a time period.
    Returns time-series data (historical metrics).
    
    Args:
        query: PromQL query string (same format as query_prometheus_instant)
        start: Start time (RFC3339 or Unix timestamp, e.g., "2024-11-10T10:00:00Z" or relative like "now-1h")
        end: End time (RFC3339 or Unix timestamp, e.g., "2024-11-10T11:00:00Z" or "now")
        step: Query resolution step width (e.g., "1m", "5m", "1h"). Default: "1m"
    
    Returns:
        JSON string with time-series metric values
    
    Examples:
        - CPU trend last hour: query="node_cpu...", start="now-1h", end="now", step="1m"
        - Memory spikes: query="container_memory...", start="now-6h", end="now", step="5m"
    """
    try:
        params = {
            "query": query,
            "start": start,
            "end": end,
            "step": step
        }
        
        response = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query_range",
            params=params,
            timeout=PROMETHEUS_TIMEOUT * 2  # Longer timeout for range queries
        )
        response.raise_for_status()
        
        result = response.json()
        
        if result.get('status') != 'success':
            return f"Query failed: {result.get('error', 'Unknown error')}"
        
        # Format response
        data = result.get('data', {})
        result_type = data.get('resultType', '')
        results = data.get('result', [])
        
        if not results:
            return f"No data returned for query: {query}"
        
        output = f"Query: {query}\n"
        output += f"Time Range: {start} to {end} (step: {step})\n"
        output += f"Result Type: {result_type}\n"
        output += f"Number of Series: {len(results)}\n\n"
        
        # Show summary for each series
        for idx, item in enumerate(results[:5]):  # Limit to first 5 series
            metric = item.get('metric', {})
            values = item.get('values', [])
            
            labels = ", ".join([f"{k}='{v}'" for k, v in metric.items()])
            metric_str = f"{{{labels}}}" if labels else "{}"
            
            output += f"Series {idx + 1}: {metric_str}\n"
            output += f"Data Points: {len(values)}\n"
            
            if values:
                # Show first, middle, last values
                output += f"  First: {values[0][1]} (at timestamp {values[0][0]})\n"
                if len(values) > 2:
                    mid = len(values) // 2
                    output += f"  Middle: {values[mid][1]} (at timestamp {values[mid][0]})\n"
                output += f"  Last: {values[-1][1]} (at timestamp {values[-1][0]})\n"
            output += "\n"
        
        if len(results) > 5:
            output += f"... and {len(results) - 5} more series\n"
        
        return output
        
    except requests.exceptions.RequestException as e:
        return f"Error connecting to Prometheus at {PROMETHEUS_URL}: {str(e)}"
    except Exception as e:
        return f"Error executing range query: {str(e)}"


@tool
def get_node_metrics(node_name: Optional[str] = None, metric_type: str = "all") -> str:
    """
    Get pre-built node metrics from Prometheus.
    Easier than writing PromQL - just specify node and metric type.
    
    Args:
        node_name: Specific node instance name (e.g., "k8s-master-001", "k8s-worker-001").
                   If None, gets metrics for all nodes.
        metric_type: Type of metric to retrieve:
            - "cpu": CPU usage percentage
            - "memory": Memory usage percentage and absolute values
            - "disk": Disk usage for root filesystem
            - "network": Network traffic (bytes in/out)
            - "all": All of the above (default)
    
    Returns:
        Formatted string with node metrics
    """
    try:
        output = f"Node Metrics Report\n"
        output += "=" * 80 + "\n"
        if node_name:
            output += f"Node: {node_name}\n\n"
        else:
            output += "All Nodes\n\n"
        
        # CPU metrics
        if metric_type in ["cpu", "all"]:
            cpu_query = "100 - (avg by(instance) (rate(node_cpu_seconds_total{mode='idle'}[5m])) * 100)"
            if node_name:
                cpu_query = f"100 - (avg(rate(node_cpu_seconds_total{{instance='{node_name}', mode='idle'}}[5m])) * 100)"
            
            response = requests.get(
                f"{PROMETHEUS_URL}/api/v1/query",
                params={"query": cpu_query},
                timeout=PROMETHEUS_TIMEOUT
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('status') == 'success':
                    results = result.get('data', {}).get('result', [])
                    output += "CPU Usage:\n"
                    output += "-" * 80 + "\n"
                    for item in results:
                        instance = item.get('metric', {}).get('instance', 'unknown')
                        value = item.get('value', [None, None])[1]
                        output += f"  {instance}: {float(value):.2f}%\n"
                    output += "\n"
        
        # Memory metrics
        if metric_type in ["memory", "all"]:
            mem_query = "(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes * 100"
            if node_name:
                mem_query = f"(node_memory_MemTotal_bytes{{instance='{node_name}'}} - node_memory_MemAvailable_bytes{{instance='{node_name}'}}) / node_memory_MemTotal_bytes{{instance='{node_name}'}} * 100"
            
            response = requests.get(
                f"{PROMETHEUS_URL}/api/v1/query",
                params={"query": mem_query},
                timeout=PROMETHEUS_TIMEOUT
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('status') == 'success':
                    results = result.get('data', {}).get('result', [])
                    output += "Memory Usage:\n"
                    output += "-" * 80 + "\n"
                    for item in results:
                        instance = item.get('metric', {}).get('instance', 'unknown')
                        value = item.get('value', [None, None])[1]
                        output += f"  {instance}: {float(value):.2f}%\n"
                    output += "\n"
        
        # Disk metrics
        if metric_type in ["disk", "all"]:
            disk_query = "(node_filesystem_size_bytes{mountpoint='/'} - node_filesystem_avail_bytes{mountpoint='/'}) / node_filesystem_size_bytes{mountpoint='/'} * 100"
            if node_name:
                disk_query = f"(node_filesystem_size_bytes{{instance='{node_name}', mountpoint='/'}} - node_filesystem_avail_bytes{{instance='{node_name}', mountpoint='/'}}) / node_filesystem_size_bytes{{instance='{node_name}', mountpoint='/'}} * 100"
            
            response = requests.get(
                f"{PROMETHEUS_URL}/api/v1/query",
                params={"query": disk_query},
                timeout=PROMETHEUS_TIMEOUT
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('status') == 'success':
                    results = result.get('data', {}).get('result', [])
                    output += "Disk Usage (root filesystem):\n"
                    output += "-" * 80 + "\n"
                    for item in results:
                        instance = item.get('metric', {}).get('instance', 'unknown')
                        value = item.get('value', [None, None])[1]
                        output += f"  {instance}: {float(value):.2f}%\n"
                    output += "\n"
        
        # Network metrics
        if metric_type in ["network", "all"]:
            net_in_query = "rate(node_network_receive_bytes_total{device!='lo'}[5m])"
            net_out_query = "rate(node_network_transmit_bytes_total{device!='lo'}[5m])"
            
            if node_name:
                net_in_query = f"rate(node_network_receive_bytes_total{{instance='{node_name}', device!='lo'}}[5m])"
                net_out_query = f"rate(node_network_transmit_bytes_total{{instance='{node_name}', device!='lo'}}[5m])"
            
            output += "Network Traffic (bytes/sec, excluding loopback):\n"
            output += "-" * 80 + "\n"
            
            # Network In
            response = requests.get(
                f"{PROMETHEUS_URL}/api/v1/query",
                params={"query": net_in_query},
                timeout=PROMETHEUS_TIMEOUT
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('status') == 'success':
                    results = result.get('data', {}).get('result', [])
                    for item in results:
                        instance = item.get('metric', {}).get('instance', 'unknown')
                        device = item.get('metric', {}).get('device', 'unknown')
                        value = item.get('value', [None, None])[1]
                        output += f"  {instance} ({device}) IN: {float(value):.2f} bytes/sec\n"
            
            # Network Out
            response = requests.get(
                f"{PROMETHEUS_URL}/api/v1/query",
                params={"query": net_out_query},
                timeout=PROMETHEUS_TIMEOUT
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('status') == 'success':
                    results = result.get('data', {}).get('result', [])
                    for item in results:
                        instance = item.get('metric', {}).get('instance', 'unknown')
                        device = item.get('metric', {}).get('device', 'unknown')
                        value = item.get('value', [None, None])[1]
                        output += f"  {instance} ({device}) OUT: {float(value):.2f} bytes/sec\n"
            output += "\n"
        
        return output
        
    except requests.exceptions.RequestException as e:
        return f"Error connecting to Prometheus at {PROMETHEUS_URL}: {str(e)}"
    except Exception as e:
        return f"Error retrieving node metrics: {str(e)}"


@tool
def get_pod_metrics(pod_name: str, namespace: Optional[str] = None, metric_type: str = "all") -> str:
    """
    Get pre-built pod/container metrics from Prometheus.
    
    Args:
        pod_name: Name of the pod to get metrics for
        namespace: Kubernetes namespace (optional, searches all namespaces if not provided)
        metric_type: Type of metric to retrieve:
            - "cpu": CPU usage
            - "memory": Memory usage
            - "network": Network traffic
            - "all": All of the above (default)
    
    Returns:
        Formatted string with pod metrics
    """
    try:
        output = f"Pod Metrics Report\n"
        output += "=" * 80 + "\n"
        output += f"Pod: {pod_name}\n"
        if namespace:
            output += f"Namespace: {namespace}\n"
        output += "\n"
        
        # CPU metrics
        if metric_type in ["cpu", "all"]:
            cpu_query = f"rate(container_cpu_usage_seconds_total{{pod='{pod_name}'}}[5m]) * 100"
            if namespace:
                cpu_query = f"rate(container_cpu_usage_seconds_total{{pod='{pod_name}', namespace='{namespace}'}}[5m]) * 100"
            
            response = requests.get(
                f"{PROMETHEUS_URL}/api/v1/query",
                params={"query": cpu_query},
                timeout=PROMETHEUS_TIMEOUT
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('status') == 'success':
                    results = result.get('data', {}).get('result', [])
                    if results:
                        output += "CPU Usage:\n"
                        output += "-" * 80 + "\n"
                        for item in results:
                            container = item.get('metric', {}).get('container', 'unknown')
                            ns = item.get('metric', {}).get('namespace', 'unknown')
                            value = item.get('value', [None, None])[1]
                            output += f"  Container: {container} (namespace: {ns})\n"
                            output += f"  CPU: {float(value):.4f}%\n\n"
                    else:
                        output += "CPU Usage: No data available\n\n"
        
        # Memory metrics
        if metric_type in ["memory", "all"]:
            mem_query = f"container_memory_usage_bytes{{pod='{pod_name}'}}"
            if namespace:
                mem_query = f"container_memory_usage_bytes{{pod='{pod_name}', namespace='{namespace}'}}"
            
            response = requests.get(
                f"{PROMETHEUS_URL}/api/v1/query",
                params={"query": mem_query},
                timeout=PROMETHEUS_TIMEOUT
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('status') == 'success':
                    results = result.get('data', {}).get('result', [])
                    if results:
                        output += "Memory Usage:\n"
                        output += "-" * 80 + "\n"
                        for item in results:
                            container = item.get('metric', {}).get('container', 'unknown')
                            ns = item.get('metric', {}).get('namespace', 'unknown')
                            value = item.get('value', [None, None])[1]
                            mem_mb = float(value) / (1024 * 1024)
                            output += f"  Container: {container} (namespace: {ns})\n"
                            output += f"  Memory: {mem_mb:.2f} MB ({value} bytes)\n\n"
                    else:
                        output += "Memory Usage: No data available\n\n"
        
        # Network metrics
        if metric_type in ["network", "all"]:
            net_in_query = f"rate(container_network_receive_bytes_total{{pod='{pod_name}'}}[5m])"
            net_out_query = f"rate(container_network_transmit_bytes_total{{pod='{pod_name}'}}[5m])"
            
            if namespace:
                net_in_query = f"rate(container_network_receive_bytes_total{{pod='{pod_name}', namespace='{namespace}'}}[5m])"
                net_out_query = f"rate(container_network_transmit_bytes_total{{pod='{pod_name}', namespace='{namespace}'}}[5m])"
            
            output += "Network Traffic:\n"
            output += "-" * 80 + "\n"
            
            # Network In
            response = requests.get(
                f"{PROMETHEUS_URL}/api/v1/query",
                params={"query": net_in_query},
                timeout=PROMETHEUS_TIMEOUT
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('status') == 'success':
                    results = result.get('data', {}).get('result', [])
                    if results:
                        for item in results:
                            value = item.get('value', [None, None])[1]
                            output += f"  Network IN: {float(value):.2f} bytes/sec\n"
            
            # Network Out
            response = requests.get(
                f"{PROMETHEUS_URL}/api/v1/query",
                params={"query": net_out_query},
                timeout=PROMETHEUS_TIMEOUT
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('status') == 'success':
                    results = result.get('data', {}).get('result', [])
                    if results:
                        for item in results:
                            value = item.get('value', [None, None])[1]
                            output += f"  Network OUT: {float(value):.2f} bytes/sec\n"
            
            output += "\n"
        
        return output
        
    except requests.exceptions.RequestException as e:
        return f"Error connecting to Prometheus at {PROMETHEUS_URL}: {str(e)}"
    except Exception as e:
        return f"Error retrieving pod metrics: {str(e)}"


@tool
def get_top_pods_by_resource(resource_type: str, namespace: Optional[str] = None, top_n: int = 10) -> str:
    """
    Get top pods by resource usage (CPU, memory, disk, network).
    Perfect for finding which pod uses the most of any resource.
    
    Args:
        resource_type: Type of resource to sort by:
            - "memory": Memory usage in bytes
            - "cpu": CPU usage percentage
            - "disk": Disk usage (filesystem)
            - "network_receive": Network receive bytes/sec
            - "network_transmit": Network transmit bytes/sec
        namespace: Kubernetes namespace to filter (optional, searches all namespaces if not provided)
        top_n: Number of top pods to return (default: 10)
    
    Returns:
        Formatted string with pod resource usage, sorted from highest to lowest
    
    Examples:
        - get_top_pods_by_resource("memory") → Find pods using most memory
        - get_top_pods_by_resource("cpu", namespace="default") → Find pods using most CPU in default namespace
        - get_top_pods_by_resource("network_receive", top_n=5) → Find top 5 pods by network traffic
    """
    try:
        # Build PromQL query based on resource type
        resource_queries = {
            "memory": "container_memory_usage_bytes{container!=''}",
            "cpu": "rate(container_cpu_usage_seconds_total{container!=''}[5m]) * 100",
            "disk": "container_fs_usage_bytes{container!=''}",
            "network_receive": "rate(container_network_receive_bytes_total{pod!=''}[5m])",
            "network_transmit": "rate(container_network_transmit_bytes_total{pod!=''}[5m])"
        }
        
        if resource_type not in resource_queries:
            return f"Invalid resource_type: '{resource_type}'. Valid options: {', '.join(resource_queries.keys())}"
        
        base_query = resource_queries[resource_type]
        
        # Add namespace filter if specified
        if namespace:
            # Insert namespace filter into the query
            base_query = base_query.replace("{", f"{{namespace='{namespace}', ")
        
        # Wrap in sort_desc to get highest values first
        query = f"sort_desc({base_query})"
        
        response = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query",
            params={"query": query},
            timeout=PROMETHEUS_TIMEOUT
        )
        response.raise_for_status()
        
        result = response.json()
        
        if result.get('status') != 'success':
            return f"Query failed: {result.get('error', 'Unknown error')}"
        
        results = result.get('data', {}).get('result', [])
        
        if not results:
            return f"No pod {resource_type} data available" + (f" in namespace '{namespace}'" if namespace else "")
        
        # Format output based on resource type
        resource_titles = {
            "memory": "Memory Usage",
            "cpu": "CPU Usage",
            "disk": "Disk Usage",
            "network_receive": "Network Receive Rate",
            "network_transmit": "Network Transmit Rate"
        }
        
        output = f"Top Pods by {resource_titles[resource_type]} (Top {min(top_n, len(results))})\n"
        output += "=" * 80 + "\n"
        if namespace:
            output += f"Namespace: {namespace}\n"
        else:
            output += "All Namespaces\n"
        output += f"Total pods/containers found: {len(results)}\n\n"
        
        output += f"Sorted by {resource_type} (highest to lowest):\n"
        output += "-" * 80 + "\n"
        
        for idx, item in enumerate(results[:top_n], 1):
            metric = item.get('metric', {})
            pod = metric.get('pod', 'unknown')
            container = metric.get('container', 'unknown')
            ns = metric.get('namespace', 'unknown')
            node = metric.get('node', 'unknown')
            value = item.get('value', [None, None])[1]
            
            output += f"{idx}. Pod: {pod}\n"
            output += f"   Container: {container}\n"
            output += f"   Namespace: {ns}\n"
            output += f"   Node: {node}\n"
            
            # Format value based on resource type
            if resource_type == "memory":
                mem_bytes = float(value)
                mem_mb = mem_bytes / (1024 * 1024)
                mem_gb = mem_bytes / (1024 * 1024 * 1024)
                if mem_gb >= 1:
                    output += f"   Memory: {mem_gb:.2f} GB ({mem_mb:.2f} MB)\n"
                else:
                    output += f"   Memory: {mem_mb:.2f} MB\n"
            
            elif resource_type == "cpu":
                cpu_percent = float(value)
                output += f"   CPU: {cpu_percent:.4f}%\n"
            
            elif resource_type == "disk":
                disk_bytes = float(value)
                disk_mb = disk_bytes / (1024 * 1024)
                disk_gb = disk_bytes / (1024 * 1024 * 1024)
                if disk_gb >= 1:
                    output += f"   Disk: {disk_gb:.2f} GB ({disk_mb:.2f} MB)\n"
                else:
                    output += f"   Disk: {disk_mb:.2f} MB\n"
            
            elif resource_type in ["network_receive", "network_transmit"]:
                bytes_per_sec = float(value)
                kb_per_sec = bytes_per_sec / 1024
                mb_per_sec = bytes_per_sec / (1024 * 1024)
                mbps = bytes_per_sec * 8 / 1000000  # Convert to Megabits per second
                
                direction = "Receive" if resource_type == "network_receive" else "Transmit"
                if mb_per_sec >= 1:
                    output += f"   Network {direction}: {mb_per_sec:.2f} MB/s ({mbps:.2f} Mbps)\n"
                else:
                    output += f"   Network {direction}: {kb_per_sec:.2f} KB/s ({mbps:.4f} Mbps)\n"
            
            output += "\n"
        
        if len(results) > top_n:
            output += f"... and {len(results) - top_n} more pods with lower {resource_type} usage\n"
        
        return output
        
    except requests.exceptions.RequestException as e:
        return f"Error connecting to Prometheus at {PROMETHEUS_URL}: {str(e)}"
    except Exception as e:
        return f"Error retrieving pod {resource_type} data: {str(e)}"


@tool
def list_available_metrics(search: Optional[str] = None) -> str:
    """
    List all available metrics in Prometheus.
    Useful for discovering what metrics are being collected.
    
    Args:
        search: Optional search string to filter metrics (case-insensitive substring match)
    
    Returns:
        List of available metric names
    """
    try:
        response = requests.get(
            f"{PROMETHEUS_URL}/api/v1/label/__name__/values",
            timeout=PROMETHEUS_TIMEOUT
        )
        response.raise_for_status()
        
        result = response.json()
        
        if result.get('status') != 'success':
            return f"Failed to retrieve metrics: {result.get('error', 'Unknown error')}"
        
        metrics = result.get('data', [])
        
        if search:
            search_lower = search.lower()
            metrics = [m for m in metrics if search_lower in m.lower()]
        
        if not metrics:
            return f"No metrics found" + (f" matching '{search}'" if search else "")
        
        output = f"Available Metrics in Prometheus\n"
        output += "=" * 80 + "\n"
        if search:
            output += f"Filtered by: '{search}'\n"
        output += f"Total: {len(metrics)} metrics\n\n"
        
        # Group by prefix for better organization
        grouped = {}
        for metric in metrics:
            prefix = metric.split('_')[0] if '_' in metric else 'other'
            if prefix not in grouped:
                grouped[prefix] = []
            grouped[prefix].append(metric)
        
        for prefix in sorted(grouped.keys()):
            output += f"\n{prefix.upper()} metrics ({len(grouped[prefix])}):\n"
            output += "-" * 80 + "\n"
            for metric in sorted(grouped[prefix])[:20]:  # Show first 20 per group
                output += f"  - {metric}\n"
            if len(grouped[prefix]) > 20:
                output += f"  ... and {len(grouped[prefix]) - 20} more\n"
        
        return output
        
    except requests.exceptions.RequestException as e:
        return f"Error connecting to Prometheus at {PROMETHEUS_URL}: {str(e)}"
    except Exception as e:
        return f"Error retrieving metrics list: {str(e)}"
