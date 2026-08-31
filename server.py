from mcp.server.mcpserver import MCPServer


# Create the MCP server
mcp = MCPServer("my-first-mcp-server")


# Create our first MCP tool
@mcp.tool()
def add_numbers(a: int, b: int) -> int:
    """Add two numbers together."""
    return a + b


# Create our second MCP tool
@mcp.tool()
def calculate(a: float, b: float, operation: str) -> float:
    """Perform a basic calculation on two numbers."""

    if operation == "add":
        return a + b

    elif operation == "subtract":
        return a - b

    elif operation == "multiply":
        return a * b

    elif operation == "divide":
        if b == 0:
            raise ValueError("Cannot divide by zero.")
        return a / b

    else:
        raise ValueError(
            "Invalid operation. Use add, subtract, multiply, or divide."
        )

# -----------------------------
# RESOURCE
# -----------------------------
@mcp.resource("customer://{customer_id}")
def get_customer(customer_id: str) -> str:
    """Get customer information by customer ID."""

    customers = {
        "1001": {
            "name": "Arun Kumar",
            "company": "ABC Technologies",
            "industry": "Software",
            "status": "Active"
        },
        "1002": {
            "name": "Priya Sharma",
            "company": "XYZ Solutions",
            "industry": "Finance",
            "status": "Active"
        },
        "1003": {
            "name": "Rahul Raj",
            "company": "TechNova",
            "industry": "Healthcare",
            "status": "Inactive"
        }
    }

    customer = customers.get(customer_id)

    if not customer:
        return f"Customer {customer_id} not found."

    return (
        f"Customer ID: {customer_id}\n"
        f"Name: {customer['name']}\n"
        f"Company: {customer['company']}\n"
        f"Industry: {customer['industry']}\n"
        f"Status: {customer['status']}"
    )




if __name__ == "__main__":
    mcp.run()