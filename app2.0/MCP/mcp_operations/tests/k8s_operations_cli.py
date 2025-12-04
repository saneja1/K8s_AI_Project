#!/usr/bin/env python3
"""
Kubernetes Operations CLI Tool
Standalone command-line interface for all 15 K8s operations tools

Usage Examples:
    python3 k8s_operations_cli.py scale-deployment nginx default --replicas 3
    python3 k8s_operations_cli.py restart-deployment nginx default --dry-run
    python3 k8s_operations_cli.py delete-pod nginx-pod default --force
    python3 k8s_operations_cli.py apply-yaml config.yaml --namespace dev
    python3 k8s_operations_cli.py drain-node worker-1 --force
"""

import sys
import os
import argparse

# Add MCP operations directory to path to import tools
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'MCP', 'mcp_operations'))

from tools_operations import (
    scale_deployment,
    restart_deployment,
    rollback_deployment,
    get_deployment_rollout_status,
    delete_pod,
    delete_pods_by_status,
    delete_pods_by_label,
    delete_deployment,
    cordon_node,
    uncordon_node,
    drain_node,
    patch_resource,
    create_namespace,
    delete_namespace,
    apply_yaml_config
)


def main():
    parser = argparse.ArgumentParser(
        description='Kubernetes Operations CLI - Manage K8s resources from command line',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Scale deployment:
    %(prog)s scale-deployment nginx default --replicas 3
    
  Restart deployment with dry-run:
    %(prog)s restart-deployment nginx default --dry-run
    
  Delete failed pods:
    %(prog)s delete-pods-by-status Failed --namespace default
    
  Apply YAML from file:
    %(prog)s apply-yaml deployment.yaml --namespace production
    
  Drain node for maintenance:
    %(prog)s drain-node worker-1 --ignore-daemonsets
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # ==================== DEPLOYMENT OPERATIONS ====================
    
    # scale-deployment
    scale_parser = subparsers.add_parser('scale-deployment', help='Scale a deployment')
    scale_parser.add_argument('name', help='Deployment name')
    scale_parser.add_argument('namespace', help='Namespace')
    scale_parser.add_argument('--replicas', type=int, required=True, help='Target replica count')
    scale_parser.add_argument('--dry-run', action='store_true', help='Test without applying')
    
    # restart-deployment
    restart_parser = subparsers.add_parser('restart-deployment', help='Restart a deployment')
    restart_parser.add_argument('name', help='Deployment name')
    restart_parser.add_argument('namespace', help='Namespace')
    restart_parser.add_argument('--dry-run', action='store_true', help='Test without applying')
    
    # rollback-deployment
    rollback_parser = subparsers.add_parser('rollback-deployment', help='Rollback a deployment')
    rollback_parser.add_argument('name', help='Deployment name')
    rollback_parser.add_argument('namespace', help='Namespace')
    rollback_parser.add_argument('--revision', type=int, help='Specific revision (optional)')
    rollback_parser.add_argument('--dry-run', action='store_true', help='Test without applying')
    
    # get-deployment-rollout-status
    status_parser = subparsers.add_parser('get-deployment-rollout-status', help='Get deployment rollout status')
    status_parser.add_argument('name', help='Deployment name')
    status_parser.add_argument('namespace', help='Namespace')
    
    # delete-deployment
    del_deploy_parser = subparsers.add_parser('delete-deployment', help='Delete a deployment')
    del_deploy_parser.add_argument('name', help='Deployment name')
    del_deploy_parser.add_argument('--namespace', default='default', help='Namespace (default: default)')
    del_deploy_parser.add_argument('--force', action='store_true', help='Force delete immediately')
    
    # ==================== POD OPERATIONS ====================
    
    # delete-pod
    del_pod_parser = subparsers.add_parser('delete-pod', help='Delete a specific pod')
    del_pod_parser.add_argument('name', help='Pod name')
    del_pod_parser.add_argument('namespace', help='Namespace')
    del_pod_parser.add_argument('--grace-period', type=int, default=30, help='Grace period in seconds (default: 30)')
    del_pod_parser.add_argument('--force', action='store_true', help='Force delete immediately')
    
    # delete-pods-by-status
    del_status_parser = subparsers.add_parser('delete-pods-by-status', help='Delete pods by status')
    del_status_parser.add_argument('status', help='Pod status (Failed, Pending, Unknown, Error, CrashLoopBackOff)')
    del_status_parser.add_argument('--namespace', default='all', help='Namespace (default: all)')
    del_status_parser.add_argument('--force', action='store_true', help='Force delete immediately')
    
    # delete-pods-by-label
    del_label_parser = subparsers.add_parser('delete-pods-by-label', help='Delete pods by label selector')
    del_label_parser.add_argument('label_selector', help='Label selector (e.g., "app=nginx")')
    del_label_parser.add_argument('--namespace', default='all', help='Namespace (default: all)')
    del_label_parser.add_argument('--force', action='store_true', help='Force delete immediately')
    
    # ==================== NODE OPERATIONS ====================
    
    # cordon-node
    cordon_parser = subparsers.add_parser('cordon-node', help='Mark node as unschedulable')
    cordon_parser.add_argument('node_name', help='Node name')
    
    # uncordon-node
    uncordon_parser = subparsers.add_parser('uncordon-node', help='Mark node as schedulable')
    uncordon_parser.add_argument('node_name', help='Node name')
    
    # drain-node
    drain_parser = subparsers.add_parser('drain-node', help='Drain a node')
    drain_parser.add_argument('node_name', help='Node name')
    drain_parser.add_argument('--force', action='store_true', help='Force drain')
    drain_parser.add_argument('--ignore-daemonsets', action='store_true', default=True, help='Ignore DaemonSet pods (default: True)')
    drain_parser.add_argument('--delete-emptydir-data', action='store_true', help='Delete pods using emptyDir volumes')
    
    # ==================== ADVANCED OPERATIONS ====================
    
    # patch-resource
    patch_parser = subparsers.add_parser('patch-resource', help='Apply JSON patch to a resource')
    patch_parser.add_argument('resource_type', help='Resource type (e.g., deployment, service)')
    patch_parser.add_argument('name', help='Resource name')
    patch_parser.add_argument('namespace', help='Namespace')
    patch_parser.add_argument('--patch-json', required=True, help='JSON patch string')
    patch_parser.add_argument('--dry-run', action='store_true', help='Test without applying')
    
    # create-namespace
    create_ns_parser = subparsers.add_parser('create-namespace', help='Create a namespace')
    create_ns_parser.add_argument('name', help='Namespace name')
    create_ns_parser.add_argument('--dry-run', action='store_true', help='Test without applying')
    
    # delete-namespace
    del_ns_parser = subparsers.add_parser('delete-namespace', help='Delete a namespace')
    del_ns_parser.add_argument('name', help='Namespace name')
    del_ns_parser.add_argument('--force', action='store_true', help='Force delete immediately')
    
    # apply-yaml-config
    apply_parser = subparsers.add_parser('apply-yaml', help='Apply YAML configuration')
    apply_parser.add_argument('yaml_file', help='Path to YAML file')
    apply_parser.add_argument('--namespace', default='default', help='Target namespace (default: default)')
    apply_parser.add_argument('--dry-run', action='store_true', help='Test without applying')
    
    # Parse arguments
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Execute the appropriate command
    result = None
    
    try:
        if args.command == 'scale-deployment':
            result = scale_deployment(args.name, args.namespace, args.replicas, args.dry_run)
        
        elif args.command == 'restart-deployment':
            result = restart_deployment(args.name, args.namespace, args.dry_run)
        
        elif args.command == 'rollback-deployment':
            result = rollback_deployment(args.name, args.namespace, args.revision, args.dry_run)
        
        elif args.command == 'get-deployment-rollout-status':
            result = get_deployment_rollout_status(args.name, args.namespace)
        
        elif args.command == 'delete-deployment':
            result = delete_deployment(args.name, args.namespace, args.force)
        
        elif args.command == 'delete-pod':
            result = delete_pod(args.name, args.namespace, args.grace_period, args.force)
        
        elif args.command == 'delete-pods-by-status':
            result = delete_pods_by_status(args.status, args.namespace, args.force)
        
        elif args.command == 'delete-pods-by-label':
            result = delete_pods_by_label(args.label_selector, args.namespace, args.force)
        
        elif args.command == 'cordon-node':
            result = cordon_node(args.node_name)
        
        elif args.command == 'uncordon-node':
            result = uncordon_node(args.node_name)
        
        elif args.command == 'drain-node':
            result = drain_node(args.node_name, args.force, args.ignore_daemonsets, args.delete_emptydir_data)
        
        elif args.command == 'patch-resource':
            result = patch_resource(args.resource_type, args.name, args.namespace, args.patch_json, args.dry_run)
        
        elif args.command == 'create-namespace':
            result = create_namespace(args.name, args.dry_run)
        
        elif args.command == 'delete-namespace':
            result = delete_namespace(args.name, args.force)
        
        elif args.command == 'apply-yaml':
            # Read YAML file
            if not os.path.exists(args.yaml_file):
                print(f"Error: YAML file '{args.yaml_file}' not found", file=sys.stderr)
                sys.exit(1)
            
            with open(args.yaml_file, 'r') as f:
                yaml_content = f.read()
            
            result = apply_yaml_config(yaml_content, args.namespace, args.dry_run)
        
        else:
            print(f"Unknown command: {args.command}", file=sys.stderr)
            parser.print_help()
            sys.exit(1)
        
        # Print result
        if result:
            print(result)
        
        sys.exit(0)
    
    except Exception as e:
        print(f"Error executing command: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
