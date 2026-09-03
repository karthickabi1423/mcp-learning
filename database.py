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
            status TEXT NOT NULL
        )
    """)

    customers = [
        (1001, "Arun Kumar", "TechNova Solutions", "Software", "Active"),
        (1002, "Priya Sharma", "GreenLeaf Industries", "Manufacturing", "Active"),
        (1003, "Ravi Kumar", "DataSphere Analytics", "Analytics", "Inactive")
    ]

    cursor.executemany("""
        INSERT OR IGNORE INTO customers
        (id, name, company, industry, status)
        VALUES (?, ?, ?, ?, ?)
    """, customers)

    connection.commit()
    connection.close()


def get_customer(customer_id):
    connection = sqlite3.connect(DATABASE_NAME)
    cursor = connection.cursor()

    cursor.execute("""
        SELECT id, name, company, industry, status
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
        SELECT id, name, company, industry, status
        FROM customers
        WHERE 1=1
    """

    parameters = []

    if industry:
        query += " AND industry = ?"
        parameters.append(industry)

    if status:
        query += " AND status = ?"
        parameters.append(status)

    cursor.execute(query, parameters)

    customers = cursor.fetchall()

    connection.close()

    return customers


if __name__ == "__main__":
    create_database()

    customers = search_customers(status="Active")

    print("Search results:")

    for customer in customers:
        print(customer)