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
            last_contacted TEXT NOT NULL,
            priority TEXT NOT NULL
        )
    """)

    # Check existing table columns for database migration
    cursor.execute("PRAGMA table_info(customers)")
    columns = [column[1] for column in cursor.fetchall()]

    if "last_contacted" not in columns:
        cursor.execute(
            "ALTER TABLE customers ADD COLUMN last_contacted TEXT"
        )

    if "priority" not in columns:
        cursor.execute(
            "ALTER TABLE customers ADD COLUMN priority TEXT"
        )

    customers = [
        (
            1001,
            "Arun Kumar",
            "TechNova Solutions",
            "Software",
            "Active",
            "2026-08-20",
            "High"
        ),
        (
            1002,
            "Priya Sharma",
            "GreenLeaf Industries",
            "Manufacturing",
            "Active",
            "2026-08-15",
            "Medium"
        ),
        (
            1003,
            "Ravi Kumar",
            "DataSphere Analytics",
            "Analytics",
            "Inactive",
            "2026-07-10",
            "Low"
        )
    ]

    cursor.executemany("""
        INSERT OR IGNORE INTO customers
        (id, name, company, industry, status, last_contacted, priority)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, customers)

    # Update existing sample customers
    cursor.execute("""
        UPDATE customers
        SET last_contacted = CASE id
            WHEN 1001 THEN '2026-08-20'
            WHEN 1002 THEN '2026-08-15'
            WHEN 1003 THEN '2026-07-10'
        END
        WHERE id IN (1001, 1002, 1003)
    """)

    cursor.execute("""
        UPDATE customers
        SET priority = CASE id
            WHEN 1001 THEN 'High'
            WHEN 1002 THEN 'Medium'
            WHEN 1003 THEN 'Low'
        END
        WHERE id IN (1001, 1002, 1003)
    """)

    connection.commit()
    connection.close()


def get_customer(customer_id):
    connection = sqlite3.connect(DATABASE_NAME)
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            id,
            name,
            company,
            industry,
            status,
            last_contacted,
            priority
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
        SELECT
            id,
            name,
            company,
            industry,
            status,
            last_contacted,
            priority,
            CAST(
                julianday('now') - julianday(last_contacted)
                AS INTEGER
            ) AS days_since_contact
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
        SELECT
            id,
            name,
            company,
            industry,
            status,
            last_contacted,
            priority,
            CAST(
                julianday('now') - julianday(last_contacted)
                AS INTEGER
            ) AS days_since_contact
        FROM customers
        WHERE status = 'Active'
        AND date(last_contacted) <= date('now', ?)
    """, (f"-{days} days",))

    customers = cursor.fetchall()

    connection.close()

    return customers

def calculate_follow_up_score(priority, days_since_contact):
    priority_weights = {
        "High": 3,
        "Medium": 2,
        "Low": 1
    }

    weight = priority_weights.get(priority, 0)

    return weight * days_since_contact


def prioritize_customers(days=14, industry=None, status="Active"):
    if days < 1:
        return []

    customers = get_customers_needing_follow_up(days)

    if industry or status:
        filtered_customers = []

        for customer in customers:
            customer_industry = customer[3]
            customer_status = customer[4]

            if industry and customer_industry.lower() != industry.lower():
                continue

            if status and customer_status.lower() != status.lower():
                continue

            filtered_customers.append(customer)

        customers = filtered_customers

    prioritized_customers = []

    for customer in customers:
        (
            customer_id,
            name,
            company,
            industry,
            status,
            last_contacted,
            priority,
            days_since_contact
        ) = customer

        follow_up_score = calculate_follow_up_score(
            priority,
            days_since_contact
        )

        prioritized_customers.append(
            (
                customer_id,
                name,
                company,
                industry,
                status,
                last_contacted,
                priority,
                days_since_contact,
                follow_up_score
            )
        )

    prioritized_customers.sort(
        key=lambda customer: customer[8],
        reverse=True
    )

    return prioritized_customers

if __name__ == "__main__":
    create_database()

    print("Customers:")

    connection = sqlite3.connect(DATABASE_NAME)
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            id,
            name,
            company,
            industry,
            status,
            last_contacted,
            priority
        FROM customers
        ORDER BY id
    """)

    customers = cursor.fetchall()

    connection.close()

    for customer in customers:
        print(customer)

    print("\nFollow-up Scores:")

    active_customers = search_customers(status="Active")

    for customer in active_customers:
        (
            customer_id,
            name,
            company,
            industry,
            status,
            last_contacted,
            priority,
            days_since_contact
        ) = customer

        score = calculate_follow_up_score(
            priority,
            days_since_contact
        )

        print(
            f"Customer {customer_id} "
            f"({name}) → Score: {score}"
        )

    print("\nPrioritized Customers:")

    customers = prioritize_customers()

    for rank, customer in enumerate(customers, start=1):
        (
            customer_id,
            name,
            company,
            industry,
            status,
            last_contacted,
            priority,
            days_since_contact,
            follow_up_score
        ) = customer

        print(
            f"{rank}. {name} "
            f"({company}) → "
            f"Score: {follow_up_score}"
        )
    print("\nPrioritized Customers — 14 days:")

    customers = prioritize_customers(14)

    for rank, customer in enumerate(customers, start=1):
        (
            customer_id,
            name,
            company,
            industry,
            status,
            last_contacted,
            priority,
            days_since_contact,
            follow_up_score
        ) = customer

        print(
            f"{rank}. {name} "
            f"({company}) → "
            f"Days: {days_since_contact}, "
            f"Score: {follow_up_score}"
        )


    print("\nPrioritized Customers — 20 days:")

    customers = prioritize_customers(20)

    for rank, customer in enumerate(customers, start=1):
        (
            customer_id,
            name,
            company,
            industry,
            status,
            last_contacted,
            priority,
            days_since_contact,
            follow_up_score
        ) = customer

        print(
            f"{rank}. {name} "
            f"({company}) → "
            f"Days: {days_since_contact}, "
            f"Score: {follow_up_score}"
        )
    print("\nInvalid Threshold Test:")
    customers = prioritize_customers(-5)
    print(customers)

    print("\nPrioritized Customers — Software + Active + 15 days:")

    customers = prioritize_customers(
        days=15,
        industry="Software",
        status="Active"
    )

    for rank, customer in enumerate(customers, start=1):
        (
            customer_id,
            name,
            company,
            industry,
            status,
            last_contacted,
            priority,
            days_since_contact,
            follow_up_score
        ) = customer

        print(
            f"{rank}. {name} ({company}) → "
            f"Industry: {industry}, "
            f"Status: {status}, "
            f"Days: {days_since_contact}, "
            f"Score: {follow_up_score}"
        )