#!/usr/bin/env python3
"""
CLI LLM Application - Communicate with Claude AI via command line
Usage: python cli_llm.py -q "Your question here"
       python cli_llm.py -q "Your question" --k8s  (for K8s supervisor agent)
"""

import os
import sys
import argparse
from dotenv import load_dotenv
from anthropic import Anthropic

# Load environment variables
load_dotenv()

def chat_with_claude(query: str, model: str = "claude-sonnet-4-20250514") -> str:
    """
    Send a query to Claude and get a response.
    
    Args:
        query: The question or prompt to send to Claude
        model: The Claude model to use (default: claude-sonnet-4-20250514)
    
    Returns:
        The response from Claude
    """
    api_key = os.getenv('ANTHROPIC_API_KEY')
    
    if not api_key:
        return "Error: ANTHROPIC_API_KEY not found in .env file"
    
    try:
        client = Anthropic(api_key=api_key)
        
        message = client.messages.create(
            model=model,
            max_tokens=4096,
            messages=[
                {"role": "user", "content": query}
            ]
        )
        
        # Extract text content from the response
        return message.content[0].text
    
    except Exception as e:
        return f"Error communicating with Claude: {str(e)}"


def chat_with_k8s_agent(query: str) -> str:
    """
    Send a query to the Kubernetes supervisor agent.
    
    Args:
        query: The question about Kubernetes cluster
    
    Returns:
        The response from the K8s agent
    """
    try:
        # Import the K8s agent
        from agents.k8s_agent import ask_k8s_agent
        
        # Query the agent
        result = ask_k8s_agent(query, verbose=False)
        
        return result.get("answer", "No response from K8s agent.")
    
    except Exception as e:
        return f"Error communicating with K8s agent: {str(e)}"


def main():
    parser = argparse.ArgumentParser(
        description='CLI tool to communicate with Claude AI or K8s Supervisor Agent',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Regular Claude AI queries
  python cli_llm.py -q "What is Kubernetes?"
  python cli_llm.py -q "Explain Docker containers" -m claude-sonnet-4-20250514
  
  # Kubernetes Supervisor Agent queries
  python cli_llm.py -q "List all pods" --k8s
  python cli_llm.py -q "Show cluster nodes" --k8s
  python cli_llm.py -q "How many pods are running on master node?" --k8s
        """
    )
    
    parser.add_argument(
        '-q', '--query',
        type=str,
        required=True,
        help='Your question or prompt'
    )
    
    parser.add_argument(
        '-m', '--model',
        type=str,
        default='claude-sonnet-4-20250514',
        help='Claude model to use (default: claude-sonnet-4-20250514)'
    )
    
    parser.add_argument(
        '--k8s',
        action='store_true',
        help='Use Kubernetes Supervisor Agent instead of Claude AI'
    )
    
    args = parser.parse_args()
    
    if args.k8s:
        print(f"\n🤖 Querying Kubernetes Supervisor Agent...\n")
        print(f"Query: {args.query}\n")
        print("=" * 80)
        
        response = chat_with_k8s_agent(args.query)
    else:
        print(f"\n🤖 Querying Claude AI...\n")
        print(f"Query: {args.query}\n")
        print("=" * 80)
        
        response = chat_with_claude(args.query, args.model)
    
    print(f"\n{response}\n")
    print("=" * 80)


if __name__ == "__main__":
    main()
