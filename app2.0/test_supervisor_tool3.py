#!/usr/bin/env python3
"""
Test complete flow: Supervisor → Monitor Agent → Tool 3
"""
from agents.k8s_agent import ask_k8s_agent

print('\n' + '='*80)
print('TESTING: Supervisor → Monitor Agent → Tool 3 (get_node_metrics)')
print('='*80)
print('\nQuestion: "Show me all metrics for my nodes"\n')

result = ask_k8s_agent('Show me all metrics for my nodes')

print('='*80)
print('SUPERVISOR RESPONSE:')
print('='*80)
print(result['answer'])
print('\n' + '='*80)

# Verify routing
if 'Monitor Agent' in result['answer']:
    print('✅ CORRECTLY ROUTED TO: Monitor Agent')
    
    # Check if data is present
    if 'CPU' in result['answer'] or 'Memory' in result['answer']:
        print('✅ CONTAINS METRICS DATA')
    else:
        print('⚠️  Routed to Monitor but no metrics in response')
else:
    print('❌ ROUTING ERROR - did not go to Monitor Agent')

print('='*80)
