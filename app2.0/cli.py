#!/usr/bin/env python3
"""
CLI for Kubernetes Cluster Query Tool
Usage: 
  Interactive mode: python cli.py
  Single query:     python cli.py -q "Your question here"
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


def interactive_mode():
    """Run in interactive mode with continuous prompts."""
    print("\n" + "=" * 80)
    print("🤖 Kubernetes AI Assistant - Interactive Mode")
    print("=" * 80)
    print("\nWelcome! Ask me anything about your Kubernetes cluster.")
    print("Commands:")
    print("  - Type your question and press Enter")
    print("  - Type 'exit', 'quit', or press Ctrl+C to exit")
    print("  - Type 'clear' to clear the screen")
    print("  - Type 'help' for examples")
    print("=" * 80 + "\n")
    
    while True:
        try:
            # Get user input
            question = input("💬 You: ").strip()
            
            # Handle special commands
            if not question:
                continue
            
            if question.lower() in ['exit', 'quit', 'q']:
                print("\n👋 Goodbye! Thanks for using the Kubernetes AI Assistant.\n")
                break
            
            if question.lower() == 'clear':
                os.system('clear' if os.name != 'nt' else 'cls')
                continue
            
            if question.lower() == 'help':
                print("\n📚 Example Questions:")
                print("  • List all pods")
                print("  • Show cluster nodes")
                print("  • How many pods are running?")
                print("  • Create a deployment named nginx-test with image nginx")
                print("  • Scale nginx-deploy-3 to 3 replicas")
                print("  • Get rollout status of nginx-deploy-3 in default namespace")
                print("  • Show CPU and memory metrics for all nodes")
                print("  • Which pods are failing?")
                print("  • Delete deployment nginx-test from default namespace\n")
                continue
            
            # Process the question
            print("\n🔍 Processing your query...\n")
            print("=" * 80)
            
            response = query_cluster(question)
            
            print(f"\n🤖 Assistant:\n{response}\n")
            print("=" * 80 + "\n")
            
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye! Thanks for using the Kubernetes AI Assistant.\n")
            break
        except EOFError:
            print("\n\n👋 Goodbye! Thanks for using the Kubernetes AI Assistant.\n")
            break
        except Exception as e:
            print(f"\n❌ Error: {str(e)}\n")
            continue


def main():
    parser = argparse.ArgumentParser(
        description='Kubernetes Cluster Query Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Interactive mode:
    python cli.py
  
  Single query mode:
    python cli.py -q "List all pods"
    python cli.py -q "Show cluster nodes"
    python cli.py -q "How many pods are running on master node?"
    python cli.py -q "Create deployment nginx-test with image nginx"
        """
    )
    
    parser.add_argument(
        '-q', '--query',
        type=str,
        required=False,
        help='Your question about the cluster (omit for interactive mode)'
    )
    
    args = parser.parse_args()
    
    # If no query provided, enter interactive mode
    if not args.query:
        interactive_mode()
    else:
        # Single query mode
        print(f"\n🔍 Query: {args.query}\n")
        print("=" * 80)
        
        response = query_cluster(args.query)
        
        print(f"\n{response}\n")
        print("=" * 80)


if __name__ == "__main__":
    main()
