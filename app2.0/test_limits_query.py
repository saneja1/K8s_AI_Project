#!/usr/bin/env python3
"""Test if Resources agent can see and use get_node_limits tool"""

import asyncio
import os
from dotenv import load_dotenv

load_dotenv()


async def test_resources_agent():
    """Test the resources agent with limits query"""
    from agents.resources_agent import create_resources_agent
    from langchain_core.messages import HumanMessage
    
    # Create agent
    agent = create_resources_agent(verbose=True)
    
    # Test query
    query = "what are CPU and memory limits on k8s-master-01?"
    print(f"🔍 Testing query: {query}\n")
    
    # Run agent
    result = await agent.ainvoke(
        {"messages": [HumanMessage(content=query)]},
        {"recursion_limit": 25}
    )
    
    # Print result
    final_message = result["messages"][-1].content
    print(f"\n📊 Agent Response:\n{final_message}")


if __name__ == "__main__":
    asyncio.run(test_resources_agent())
