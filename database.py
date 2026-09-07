import sqlite3

DATABASE_NAME = "customers.db"


def create_database():
    connection = sqlite3.connect(DATABASE_NAME)
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            company TEXT NOT NULL,
            industry TEXT NOT NULL,
            status TEXT NOT NULL,
            last_contacted TEXT NOT NULL
        )
    """)
    cursor.execute("PRAGMA table_info(customers)")
    columns = [column[1] for column in cursor.fetchall()]

    if "last_contacted" not in columns:
        cursor.execute(
            "ALTER TABLE customers ADD COLUMN last_contacted TEXT"
        )

    customers = [
        (1001, "Arun Kumar", "TechNova Solutions", "Software", "Active", "2026-08-20"),
        (1002, "Priya Sharma", "GreenLeaf Industries", "Manufacturing", "Active", "2026-08-15"),
        (1003, "Ravi Kumar", "DataSphere Analytics", "Analytics", "Inactive", "2026-07-10")
    ]

    cursor.executemany("""
        INSERT OR IGNORE INTO customers
        (id, name, company, industry, status, last_contacted)
        VALUES (?, ?, ?, ?, ?, ?)
    """, customers)

    cursor.execute("""
    UPDATE customers
    SET last_contacted = CASE id
        WHEN 1001 THEN '2026-08-20'
        WHEN 1002 THEN '2026-08-15'
        WHEN 1003 THEN '2026-07-10'
    END
    WHERE id IN (1001, 1002, 1003)
""")

    connection.commit()
    connection.close()


def get_customer(customer_id):
    connection = sqlite3.connect(DATABASE_NAME)
    cursor = connection.cursor()

    cursor.execute("""
        SELECT id, name, company, industry, status, last_contacted
        FROM customers
        WHERE id = ?
    """, (customer_id,))

    customer = cursor.fetchone()

    connection.close()

    return customer


def search_customers(industry=None, status=None):
    connection = sqlite3.connect(DATABASE_NAME)
    cursor = connection.cursor()

    query = """
        SELECT id, name, company, industry, status, last_contacted
        FROM customers
        WHERE 1=1
        """

    parameters = []

    if industry:
        query += " AND LOWER(industry) = LOWER(?)"
        parameters.append(industry)

    if status:
        query += " AND LOWER(status) = LOWER(?)"
        parameters.append(status)

    cursor.execute(query, parameters)

    customers = cursor.fetchall()

    connection.close()

    return customers


def get_customers_needing_follow_up(days=14):
    connection = sqlite3.connect(DATABASE_NAME)
    cursor = connection.cursor()

    cursor.execute("""
        SELECT id, name, company, industry, status, last_contacted
        FROM customers
        WHERE status = 'Active'
        AND date(last_contacted) <= date('now', ?)
    """, (f"-{days} days",))

    customers = cursor.fetchall()

    connection.close()

    return customers


if __name__ == "__main__":
    create_database()

    customers = search_customers(status="Active")

    print("Search results:")

    for customer in customers:
        print(customer)