"""
Kubernetes Tools Organized by Agent Domain

This module imports all tools from utils/langchain_tools.py and organizes them
by specialist agent for clean separation of concerns.

The hybrid approach uses:
- 21 specialized tools with custom logic, parsing, and workflows
- 1 generic execute_kubectl tool shared across ALL agents for edge cases
"""

from utils.langchain_tools import (
    # Core tools
    get_cluster_resources,
    describe_resource,
    get_pod_logs,
    check_node_health,
    check_cluster_health,
    
    # Generic tool (shared by ALL agents)
    execute_kubectl,
    
    # Monitor tools
    get_cluster_events,
    troubleshoot_pod,
    
    # Security tools
    check_rbac_permissions,
    list_secrets_and_configmaps,
    check_network_policies,
    
    # Resources tools
    get_resource_usage,
    get_resource_quotas,
    analyze_resource_requests,
    
    # Operations tools
    delete_pod,
    scale_deployment,
    restart_deployment,
    delete_failed_pods,
    cordon_drain_node,
    create_configmap,
    create_secret,
    apply_manifest
)

# =============================================================================
# HEALTH AGENT TOOLS - Node and cluster health monitoring
# =============================================================================
HEALTH_TOOLS = [
    check_node_health,      # Check specific node (conditions, taints, capacity)
    check_cluster_health,   # Overview of all nodes (status, roles, IPs)
    execute_kubectl         # Generic kubectl for health commands (get nodes, componentstatuses)
]

# =============================================================================
# SECURITY AGENT TOOLS - Security policies, RBAC, secrets
# =============================================================================
SECURITY_TOOLS = [
    check_rbac_permissions,         # Check user/SA permissions (resources + verbs)
    list_secrets_and_configmaps,    # List secrets/configmaps WITHOUT showing values
    check_network_policies,         # List network policies (pod firewall rules)
    execute_kubectl                 # Generic kubectl for security commands (rolebindings, auth)
]

# =============================================================================
# RESOURCES AGENT TOOLS - CPU/Memory monitoring and resource usage
# =============================================================================
RESOURCES_TOOLS = [
    get_resource_usage,         # kubectl top nodes/pods with usage analysis
    get_resource_quotas,        # Check namespace quotas (hard limits vs used)
    analyze_resource_requests,  # Compare requested vs actual usage efficiency
    execute_kubectl             # Generic kubectl for resource commands (top, describe quota)
]

# =============================================================================
# MONITOR AGENT TOOLS - Logs, events, and troubleshooting
# =============================================================================
MONITOR_TOOLS = [
    get_pod_logs,           # Get logs with partial name matching support
    get_cluster_events,     # Recent events sorted by time (warnings, errors)
    troubleshoot_pod,       # Complete pod analysis: status + logs + events + describe
    execute_kubectl         # Generic kubectl for monitoring (logs --previous, events filters)
]

# =============================================================================
# DESCRIBE-GET AGENT TOOLS - List and describe resources
# =============================================================================
DESCRIBE_GET_TOOLS = [
    get_cluster_resources,  # List any K8s resource (pods, services, deployments, etc.)
    describe_resource,      # Get detailed info about specific resource (with smart parsing)
    execute_kubectl         # Generic kubectl for listing (get all, get crd, api-resources)
]

# =============================================================================
# OPERATIONS AGENT TOOLS - Delete, scale, restart, create (WITH CONFIRMATIONS)
# =============================================================================
OPERATIONS_TOOLS = [
    delete_pod,             # Delete pod with confirmation and validation
    scale_deployment,       # Scale deployment with confirmation and progress tracking
    restart_deployment,     # Rollout restart with confirmation and monitoring
    delete_failed_pods,     # Clean up failed/completed pods with confirmation (max 50)
    cordon_drain_node,      # Cordon/drain/uncordon node with confirmation
    create_configmap,       # Create ConfigMap with confirmation
    create_secret,          # Create Secret with confirmation (values masked)
    apply_manifest,         # Apply YAML manifest with confirmation
    execute_kubectl         # Generic kubectl for operations (apply, patch, rollout)
]

# =============================================================================
# ALL TOOLS COMBINED - For backward compatibility
# =============================================================================
ALL_TOOLS = (
    HEALTH_TOOLS +
    SECURITY_TOOLS +
    RESOURCES_TOOLS +
    MONITOR_TOOLS +
    DESCRIBE_GET_TOOLS +
    OPERATIONS_TOOLS
)

# =============================================================================
# TOOL COUNT SUMMARY
# =============================================================================
# Specialized tools: 21 (with custom logic, parsing, confirmations)
# Generic tool: 1 (execute_kubectl - shared across ALL agents)
# Total unique tools: 22
# 
# Note: execute_kubectl appears in each agent's tool list but is the SAME tool
#       (not 6 different tools). It's shared for flexibility and edge cases.
# =============================================================================
