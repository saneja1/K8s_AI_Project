#!/usr/bin/env python3
"""
CLI for Kubernetes Cluster Query Tool
Usage: python cli.py -q "Your question here"
"""

import os
import sys
import argparse
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def query_cluster(question: str) -> str:
    """
    Send a query about the Kubernetes cluster.
    
    Args:
        question: Question about the cluster
    
    Returns:
        Response with cluster information
    """
    try:
        from agents.k8s_agent import ask_k8s_agent
        
        result = ask_k8s_agent(question, verbose=False)
        return result.get("answer", "No response available.")
    
    except Exception as e:
        return f"Error: {str(e)}"


def main():
    parser = argparse.ArgumentParser(
        description='Kubernetes Cluster Query Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli.py -q "List all pods"
  python cli.py -q "Show cluster nodes"
  python cli.py -q "How many pods are running on master node?"
  python cli.py -q "How many running pods in kube-system namespace?"
        """
    )
    
    parser.add_argument(
        '-q', '--query',
        type=str,
        required=True,
        help='Your question about the cluster'
    )
    
    args = parser.parse_args()
    
    print(f"\n🔍 Query: {args.query}\n")
    print("=" * 80)
    
    response = query_cluster(args.query)
    
    print(f"\n{response}\n")
    print("=" * 80)


if __name__ == "__main__":
    main()
