from mcp.server.mcpserver import MCPServer
from database import( get_customer as get_customer_from_db,search_customers as search_customers_from_db)
from typing import Literal

# Create the MCP server
mcp = MCPServer("my-first-mcp-server")


# Create our first MCP tool
@mcp.tool()
def add_numbers(a: int, b: int) -> int:
    """Add two numbers together """
    return a + b


# Create our second MCP tool
@mcp.tool()
def calculate(
    a: float,
    b: float,
    operation: Literal["add", "subtract", "multiply", "divide"]
) -> float:
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

    
@mcp.tool()
def search_customers(
    industry: str = "",
    status: str = ""
) -> str:
    """Search customers by industry and/or status"""

    customers = search_customers_from_db(
        industry=industry or None,
        status=status or None
    )

    if not customers:
        return "No customers found."

    results = []

    for customer in customers:
        customer_id, name, company, industry, status = customer

        results.append(
            f"Customer ID: {customer_id}\n"
            f"Name: {name}\n"
            f"Company: {company}\n"
            f"Industry: {industry}\n"
            f"Status: {status}"
        )

    return "\n\n".join(results)

# Resources

@mcp.resource("customer://{customer_id}")
def customer_resource(customer_id: str) -> str:
    """Retrieve customer information from the SQLite database."""
    customer = get_customer_from_db(int(customer_id))

    if customer is None:
        return f"Customer with ID {customer_id} was not found."

    customer_id, name, company, industry, status = customer

    return f"""
Customer ID: {customer_id}
Name: {name}
Company: {company}
Industry: {industry}
Status: {status}
"""



#Prompt

@mcp.prompt()
def analyze_customer(customer_id: str) -> str:
    """Create an analysis prompt for a customer"""

    return f"""
Analyze the customer with ID {customer_id}.

Please provide:

1. Customer summary
2. Company and industry analysis
3. Current customer status
4. Potential business opportunities
5. Recommended next action

Keep the analysis concise and practical.
"""


if __name__ == "__main__":
    mcp.run()