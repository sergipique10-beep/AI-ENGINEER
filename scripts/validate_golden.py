"""Validate the golden dataset."""
import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

with open('data/golden.json') as f:
    cases = json.load(f)

print(f'Total cases: {len(cases)}')
cats = {}
diffs = {}
refuse_count = 0
for c in cases:
    cat = c['category']
    cats[cat] = cats.get(cat, 0) + 1
    d = c['difficulty']
    diffs[d] = diffs.get(d, 0) + 1
    if c['should_refuse']:
        refuse_count += 1

print('\nBy category:')
for k, v in sorted(cats.items()):
    pct = v / len(cases) * 100
    print(f'  {k}: {v} ({pct:.1f}%)')

print('\nBy difficulty:')
for k, v in sorted(diffs.items()):
    print(f'  {k}: {v}')

print(f'\nshould_refuse=true: {refuse_count}')

# Check unique IDs
ids = [c['id'] for c in cases]
if len(ids) != len(set(ids)):
    print('ERROR: Duplicate IDs found!')
else:
    print('All IDs unique.')

# Check required fields
required = ['id', 'input', 'expected_tools', 'acceptance_criteria', 'category', 'difficulty', 'should_refuse']
errors = 0
for c in cases:
    for field in required:
        if field not in c:
            print(f'ERROR: Missing field {field} in case {c.get("id", "???")}')
            errors += 1
if errors == 0:
    print('All required fields present.')

# Verify numeric values against DB
import sqlite3
conn = sqlite3.connect('data/store.db')

# Check case r001
r = conn.execute('''
    SELECT ROUND(SUM(oi.quantity * oi.unit_price), 2) as total
    FROM order_items oi JOIN orders o ON oi.order_id = o.id WHERE o.status = 'completed'
''').fetchone()
db_revenue = r[0]
print(f'\nDB total completed revenue: ${db_revenue}')

# Check case r002
r = conn.execute('SELECT COUNT(*) FROM customers').fetchone()
print(f'DB customer count: {r[0]}')

# Check case r006
r = conn.execute('SELECT COUNT(*) FROM orders WHERE status="pending"').fetchone()
print(f'DB pending orders: {r[0]}')

conn.close()
print('\nValidation complete.')
