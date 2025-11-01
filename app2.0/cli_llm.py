#!/usr/bin/env python3
"""
CLI LLM Application - Communicate with Claude AI via command line
Usage: python cli_llm.py -q "Your question here"
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


def main():
    parser = argparse.ArgumentParser(
        description='CLI tool to communicate with Claude AI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli_llm.py -q "What is Kubernetes?"
  python cli_llm.py -q "Explain Docker containers" -m claude-sonnet-4-20250514
        """
    )
    
    parser.add_argument(
        '-q', '--query',
        type=str,
        required=True,
        help='Your question or prompt for Claude'
    )
    
    parser.add_argument(
        '-m', '--model',
        type=str,
        default='claude-sonnet-4-20250514',
        help='Claude model to use (default: claude-sonnet-4-20250514)'
    )
    
    args = parser.parse_args()
    
    print(f"\n🤖 Querying Claude AI...\n")
    print(f"Query: {args.query}\n")
    print("=" * 80)
    
    response = chat_with_claude(args.query, args.model)
    
    print(f"\n{response}\n")
    print("=" * 80)


if __name__ == "__main__":
    main()
