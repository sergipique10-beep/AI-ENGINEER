"""Dump DB stats for golden dataset creation."""
import sys, io, sqlite3
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
conn = sqlite3.connect('data/store.db')
conn.row_factory = sqlite3.Row

print('=== CUSTOMERS ===')
r = conn.execute('SELECT COUNT(*) as n, COUNT(DISTINCT country) as countries FROM customers').fetchone()
print(f'Total: {r["n"]}, Countries: {r["countries"]}')
rows = conn.execute('SELECT country, COUNT(*) as n FROM customers GROUP BY country ORDER BY n DESC').fetchall()
for row in rows: print(f'  {row["country"]}: {row["n"]}')

print('\n=== PRODUCTS ===')
rows = conn.execute('SELECT id, name, category, price, cost, ROUND((price-cost)/price*100, 1) as margin_pct FROM products').fetchall()
for row in rows:
    print(f'  {row["id"]}: {row["name"]} | {row["category"]} | ${row["price"]} / ${row["cost"]} | margin {row["margin_pct"]}%')

print('\n=== ORDERS ===')
rows = conn.execute('SELECT status, COUNT(*) as n FROM orders GROUP BY status').fetchall()
for row in rows: print(f'  {row["status"]}: {row["n"]}')
r = conn.execute('SELECT MIN(order_date) as min_d, MAX(order_date) as max_d FROM orders').fetchone()
print(f'  Date range: {r["min_d"]} to {r["max_d"]}')

print('\n=== REVENUE BY STATUS ===')
rows = conn.execute('''
    SELECT o.status, ROUND(SUM(oi.quantity * oi.unit_price), 2) as revenue
    FROM orders o JOIN order_items oi ON o.id = oi.order_id
    GROUP BY o.status ORDER BY revenue DESC
''').fetchall()
for row in rows: print(f'  {row["status"]}: ${row["revenue"]}')

print('\n=== TOP PRODUCTS BY UNITS SOLD ===')
rows = conn.execute('''
    SELECT p.name, SUM(oi.quantity) as total_qty
    FROM order_items oi JOIN products p ON oi.product_id = p.id
    GROUP BY p.name ORDER BY total_qty DESC LIMIT 5
''').fetchall()
for row in rows: print(f'  {row["name"]}: {row["total_qty"]} units')

print('\n=== ORDERS PER YEAR ===')
rows = conn.execute('''
    SELECT strftime('%Y', order_date) as yr, COUNT(*) as n FROM orders GROUP BY yr
''').fetchall()
for row in rows: print(f'  {row["yr"]}: {row["n"]} orders')

print('\n=== REVENUE BY CATEGORY (completed) ===')
rows = conn.execute('''
    SELECT p.category, ROUND(SUM(oi.quantity * oi.unit_price), 2) as revenue
    FROM order_items oi JOIN products p ON oi.product_id = p.id
    JOIN orders o ON oi.order_id = o.id WHERE o.status = 'completed'
    GROUP BY p.category ORDER BY revenue DESC
''').fetchall()
for row in rows: print(f'  {row["category"]}: ${row["revenue"]}')

print('\n=== TOTAL REVENUE ALL COMPLETED ===')
r = conn.execute('''
    SELECT ROUND(SUM(oi.quantity * oi.unit_price), 2) as total
    FROM order_items oi JOIN orders o ON oi.order_id = o.id WHERE o.status = 'completed'
''').fetchone()
print(f'  ${r["total"]}')

print('\n=== CUSTOMERS WITH MOST ORDERS ===')
rows = conn.execute('''
    SELECT c.name, COUNT(o.id) as n_orders
    FROM customers c JOIN orders o ON c.id = o.customer_id
    GROUP BY c.name ORDER BY n_orders DESC LIMIT 5
''').fetchall()
for row in rows: print(f'  {row["name"]}: {row["n_orders"]} orders')

print('\n=== AVERAGE ORDER VALUE ===')
r = conn.execute('''
    SELECT ROUND(AVG(order_total), 2) as avg_val FROM (
        SELECT o.id, SUM(oi.quantity * oi.unit_price) as order_total
        FROM orders o JOIN order_items oi ON o.id = oi.order_id
        WHERE o.status = 'completed' GROUP BY o.id
    )
''').fetchone()
print(f'  ${r["avg_val"]}')

print('\n=== ORDERS WITH >3 ITEMS ===')
r = conn.execute('''
    SELECT COUNT(*) as n FROM (
        SELECT o.id FROM orders o JOIN order_items oi ON o.id = oi.order_id
        GROUP BY o.id HAVING COUNT(*) > 3
    )
''').fetchone()
print(f'  {r["n"]} orders')

conn.close()
