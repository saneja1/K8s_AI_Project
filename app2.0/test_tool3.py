#!/usr/bin/env python3
from agents.k8s_agent import ask_k8s_agent

print('\n' + '='*80)
print('TEST: Node Metrics Query (Should route to MONITOR agent with Tool 3)')
print('='*80)
print('\nQuestion: Show me all metrics for my nodes\n')

result = ask_k8s_agent('Show me all metrics for my nodes')

print('='*80)
print('RESPONSE:')
print('='*80)
print(result['answer'])
print('='*80)
