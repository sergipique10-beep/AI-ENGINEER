"""Generate synthetic data and populate the SQLite database."""

from __future__ import annotations

import random
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from .schema import SCHEMA_SQL

# Reproducible randomness
random.seed(42)

# --- Reference data ---

COUNTRIES = ["US", "ES", "DE", "FR", "UK", "IT", "NL", "MX", "BR", "AR"]
STATUSES = ["completed"] * 7 + ["pending"] * 2 + ["cancelled"] * 1  # weighted

PRODUCTS = [
    # (name, category, price, cost)
    ("Mechanical Keyboard Pro", "Periféricos", 129.99, 65.00),
    ("Gaming Mouse X1", "Periféricos", 79.99, 32.00),
    ("Ultra-Wide Monitor 34\"", "Monitores", 549.99, 320.00),
    ("4K Monitor 27\"", "Monitores", 399.99, 230.00),
    ("USB-C Hub 7-in-1", "Accesorios", 49.99, 18.00),
    ("Webcam HD 1080p", "Accesorios", 69.99, 28.00),
    ("Noise-Cancelling Headphones", "Audio", 199.99, 85.00),
    ("Bluetooth Speaker Mini", "Audio", 39.99, 15.00),
    ("Laptop Stand Adjustable", "Accesorios", 34.99, 12.00),
    ("SSD 1TB NVMe", "Almacenamiento", 89.99, 45.00),
    ("External HDD 2TB", "Almacenamiento", 64.99, 30.00),
    ("Wireless Charger Pad", "Accesorios", 24.99, 9.00),
    ("Mechanical Numpad", "Periféricos", 39.99, 16.00),
    ("Monitor Light Bar", "Accesorios", 44.99, 17.00),
    ("Ergonomic Chair Mat", "Accesorios", 29.99, 10.00),
]

CUSTOMER_NAMES = [
    "Alice Johnson", "Bob Martinez", "Carol Schmidt", "David Lee",
    "Emma Wilson", "Frank Garcia", "Grace Kim", "Henry Brown",
    "Iris Dubois", "Jack Thompson", "Karen Silva", "Liam O'Brien",
    "Mia Fernandez", "Noah Weber", "Olivia Patel", "Paul Anderson",
    "Quinn Rossi", "Rosa Hernandez", "Sofia Nguyen", "Tom Baker",
    "Uma Sharma", "Victor Larsson", "Wendy Fischer", "Xavier Moreau",
    "Yuki Tanaka", "Zara Ali", "Adrian Cruz", "Bea Jansen",
    "Carlos Mendez", "Diana Volkov",
]


def _random_date(start: datetime, end: datetime) -> datetime:
    delta = end - start
    random_days = random.randint(0, delta.days)
    random_seconds = random.randint(0, 86399)
    return start + timedelta(days=random_days, seconds=random_seconds)


def seed_database(db_path: Path, *, force: bool = False) -> None:
    """Create and populate the database. Skips if it exists unless force=True."""
    if db_path.exists() and not force:
        print(f"Database already exists at {db_path}, skipping seed. Use --force to recreate.")
        return

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.executescript(SCHEMA_SQL)

    # --- Insert customers ---
    start_date = datetime(2023, 1, 1)
    end_date = datetime(2026, 8, 1)
    customers = []
    for i, name in enumerate(CUSTOMER_NAMES, 1):
        country = random.choice(COUNTRIES)
        signup = _random_date(start_date, end_date).strftime("%Y-%m-%d")
        customers.append((i, name, country, signup))
    conn.executemany("INSERT INTO customers VALUES (?, ?, ?, ?)", customers)

    # --- Insert products ---
    products = []
    for i, (name, category, price, cost) in enumerate(PRODUCTS, 1):
        products.append((i, name, category, price, cost))
    conn.executemany("INSERT INTO products VALUES (?, ?, ?, ?, ?)", products)

    # --- Insert orders + order_items ---
    order_id = 0
    order_items = []
    order_date_range = (datetime(2024, 1, 1), datetime(2026, 9, 1))
    orders = []

    for _ in range(250):
        order_id += 1
        cust_id = random.randint(1, len(CUSTOMER_NAMES))
        odate = _random_date(*order_date_range).strftime("%Y-%m-%d")
        status = random.choice(STATUSES)
        orders.append((order_id, cust_id, odate, status))

        # 1-5 items per order
        n_items = random.randint(1, 5)
        used_products = set()
        for _ in range(n_items):
            prod_id = random.randint(1, len(PRODUCTS))
            while prod_id in used_products:
                prod_id = random.randint(1, len(PRODUCTS))
            used_products.add(prod_id)
            qty = random.randint(1, 4)
            # Use current product price as unit_price (simulates price at time of sale)
            unit_price = products[prod_id - 1][3]
            order_items.append((len(order_items) + 1, order_id, prod_id, qty, unit_price))

    conn.executemany("INSERT INTO orders VALUES (?, ?, ?, ?)", orders)
    conn.executemany("INSERT INTO order_items VALUES (?, ?, ?, ?, ?)", order_items)

    conn.commit()
    conn.close()
    print(f"Database seeded at {db_path}: {len(customers)} customers, {len(products)} products, {len(orders)} orders, {len(order_items)} order_items.")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    from store_analytics.config import DATABASE_PATH
    force = "--force" in sys.argv
    seed_database(DATABASE_PATH, force=force)
