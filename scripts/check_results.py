"""Check eval results details."""
import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

with open('data/eval_results.json') as f:
    data = json.load(f)

for c in data['cases']:
    print(f'{c["id"]}: tool_sel={c["tool_selection"]}, task_comp={c["task_completion"]}')
    print(f'  answer: {c["final_answer"][:150]}')
    print(f'  task_details: {c["task_completion_details"][:150]}')
    print()
