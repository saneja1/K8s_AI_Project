#!/usr/bin/env python3
"""
Test script to ask 2 questions to each of the 5 specialized agents
"""

import os
import sys
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents.health_agent import ask_health_agent
from agents.describe_agent import ask_describe_agent
from agents.resources_agent import ask_resources_agent
from agents.monitor_agent import ask_monitor_agent
from agents.operations_agent import run_operations_agent

# Load environment variables
load_dotenv()

def print_separator(title):
    """Print a nice separator"""
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80 + "\n")

def test_agent(agent_name, agent_func, questions, is_operations=False):
    """Test an agent with given questions"""
    print_separator(f"{agent_name.upper()} - Testing with 2 Questions")
    
    for i, question in enumerate(questions, 1):
        print(f"\n📝 Question {i}: {question}")
        print("-" * 80)
        
        try:
            if is_operations:
                # Operations agent returns string directly
                response = agent_func(question)
                print(f"✅ Answer:\n{response}\n")
            else:
                # Other agents return dict with 'answer' key
                response = agent_func(question)
                answer = response.get('answer', 'No answer returned')
                print(f"✅ Answer:\n{answer}\n")
        except Exception as e:
            print(f"❌ Error: {str(e)}\n")
        
        print("-" * 80)

def main():
    """Run all agent tests"""
    print_separator("🚀 TESTING 5 KUBERNETES AGENTS - 2 QUESTIONS EACH")
    
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        print("❌ Error: ANTHROPIC_API_KEY not set in environment")
        return
    
    # ========================================================================
    # AGENT 1: HEALTH AGENT
    # ========================================================================
    health_questions = [
        "What is the health status of all nodes in the cluster?",
        "Are there any cluster-level issues or events I should know about?"
    ]
    test_agent(
        "Health Agent",
        lambda q: ask_health_agent(q, api_key=api_key, verbose=False),
        health_questions
    )
    
    # ========================================================================
    # AGENT 2: DESCRIBE AGENT
    # ========================================================================
    describe_questions = [
        "List all pods in the default namespace",
        "How many deployments are currently in the cluster?"
    ]
    test_agent(
        "Describe Agent",
        lambda q: ask_describe_agent(q, api_key=api_key, verbose=False),
        describe_questions
    )
    
    # ========================================================================
    # AGENT 3: RESOURCES AGENT
    # ========================================================================
    resources_questions = [
        "Show me the current resource allocation using kubectl top",
        "What are the resource limits and requests for all pods?"
    ]
    test_agent(
        "Resources Agent",
        lambda q: ask_resources_agent(q, api_key=api_key, verbose=False),
        resources_questions
    )
    
    # ========================================================================
    # AGENT 4: MONITOR AGENT
    # ========================================================================
    monitor_questions = [
        "What is the current CPU and memory usage for all nodes?",
        "Which pod is using the most memory right now?"
    ]
    test_agent(
        "Monitor Agent",
        lambda q: ask_monitor_agent(q, api_key=api_key, verbose=False),
        monitor_questions
    )
    
    # ========================================================================
    # AGENT 5: OPERATIONS AGENT
    # ========================================================================
    operations_questions = [
        "List all deployments in the cluster",
        "Show me information about the kube-system namespace"
    ]
    test_agent(
        "Operations Agent",
        lambda q: run_operations_agent(q, api_key=api_key),
        operations_questions,
        is_operations=True
    )
    
    print_separator("✅ ALL TESTS COMPLETED")

if __name__ == "__main__":
    main()
