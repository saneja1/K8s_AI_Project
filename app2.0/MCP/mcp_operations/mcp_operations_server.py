"""
MCP Operations Server
Exposes Kubernetes operations tools via MCP protocol
Port: 8003
"""

import os
from mcp.server.fastmcp import FastMCP
from tools_operations import (
    scale_deployment,
    restart_deployment,
    rollback_deployment,
    get_deployment_rollout_status,
    delete_pod,
    delete_pods_by_status,
    delete_pods_by_label,
    cordon_node,
    uncordon_node,
    drain_node,
    patch_resource,
    create_namespace,
    delete_namespace,
    apply_yaml_config
)

# Get port from environment or default to 8003
port = int(os.getenv('PORT', '8003'))

# Initialize MCP server with explicit port
mcp = FastMCP("K8s-Operations", port=port)

# Wrap and register all tools using FastMCP decorator
@mcp.tool()
def scale_deployment_tool(name: str, namespace: str, replicas: int, dry_run: bool = False) -> str:
    """Scale a deployment to specified number of replicas."""
    return scale_deployment(name, namespace, replicas, dry_run)

@mcp.tool()
def restart_deployment_tool(name: str, namespace: str, dry_run: bool = False) -> str:
    """Restart (rollout restart) a deployment by recreating pods."""
    return restart_deployment(name, namespace, dry_run)

@mcp.tool()
def rollback_deployment_tool(name: str, namespace: str, revision: int = None, dry_run: bool = False) -> str:
    """Rollback a deployment to previous revision or specific revision."""
    return rollback_deployment(name, namespace, revision, dry_run)

@mcp.tool()
def get_deployment_rollout_status_tool(name: str, namespace: str) -> str:
    """Get the rollout status of a deployment."""
    return get_deployment_rollout_status(name, namespace)

@mcp.tool()
def delete_pod_tool(name: str, namespace: str, grace_period: int = 30, force: bool = False) -> str:
    """Delete a specific pod."""
    return delete_pod(name, namespace, grace_period, force)

@mcp.tool()
def delete_pods_by_status_tool(status: str, namespace: str = "all", force: bool = False) -> str:
    """Delete all pods with specific status (Failed, Pending, Unknown, Error, CrashLoopBackOff)."""
    return delete_pods_by_status(status, namespace, force)

@mcp.tool()
def delete_pods_by_label_tool(label_selector: str, namespace: str = "all", force: bool = False) -> str:
    """Delete all pods matching a label selector."""
    return delete_pods_by_label(label_selector, namespace, force)

@mcp.tool()
def cordon_node_tool(node_name: str) -> str:
    """Mark a node as unschedulable (cordon)."""
    return cordon_node(node_name)

@mcp.tool()
def uncordon_node_tool(node_name: str) -> str:
    """Mark a node as schedulable (uncordon)."""
    return uncordon_node(node_name)

@mcp.tool()
def drain_node_tool(node_name: str, force: bool = False, ignore_daemonsets: bool = True, delete_emptydir_data: bool = False) -> str:
    """Drain a node by safely evicting all pods."""
    return drain_node(node_name, force, ignore_daemonsets, delete_emptydir_data)

@mcp.tool()
def patch_resource_tool(resource_type: str, name: str, namespace: str, patch_json: str, dry_run: bool = False) -> str:
    """Apply a JSON patch to any Kubernetes resource."""
    return patch_resource(resource_type, name, namespace, patch_json, dry_run)

@mcp.tool()
def create_namespace_tool(name: str, dry_run: bool = False) -> str:
    """Create a new Kubernetes namespace."""
    return create_namespace(name, dry_run)

@mcp.tool()
def delete_namespace_tool(name: str, force: bool = False) -> str:
    """Delete a Kubernetes namespace and all resources within it."""
    return delete_namespace(name, force)

@mcp.tool()
def apply_yaml_config_tool(yaml_content: str, namespace: str = "default", dry_run: bool = False) -> str:
    """Apply YAML configuration to create or update any Kubernetes resource (pods, deployments, services, configmaps, secrets, etc)."""
    return apply_yaml_config(yaml_content, namespace, dry_run)

if __name__ == "__main__":
    # Run server on HTTP transport
    # Port should be set via PORT environment variable when launching this script
    # Example: PORT=8003 python3 mcp_operations_server.py
    mcp.run(transport="streamable-http")
