from mcp.server.mcpserver import MCPServer
from database import(
    get_customer as get_customer_from_db,
    search_customers as search_customers_from_db,
    get_customers_needing_follow_up as get_customers_needing_follow_up_from_db
)

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
) -> float | str:
    """Perform a basic calculation on two numbers."""
    if operation == "add":
        return a + b

    elif operation == "subtract":
        return a - b

    elif operation == "multiply":
        return a * b

    elif operation == "divide":
        if b == 0:
            return "Error: Cannot divide by zero."

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
        customer_id, name, company, industry, status, last_contacted = customer

        results.append(
            f"Customer ID: {customer_id}\n"
            f"Name: {name}\n"
            f"Company: {company}\n"
            f"Industry: {industry}\n"
            f"Status: {status}\n"
            f"Last Contacted: {last_contacted}"
        )

    return "\n\n".join(results)


@mcp.tool()
def get_customers_needing_follow_up(days: int = 14) -> str:
    """Find active customers who have not been contacted recently."""

    customers = get_customers_needing_follow_up_from_db(days)

    if not customers:
        return "No customers need follow-up."

    results = []

    for customer in customers:
        (
            customer_id,
            name,
            company,
            industry,
            status,
            last_contacted
        ) = customer

        results.append(
            f"Customer ID: {customer_id}\n"
            f"Name: {name}\n"
            f"Company: {company}\n"
            f"Industry: {industry}\n"
            f"Status: {status}\n"
            f"Last Contacted: {last_contacted}"
        )

    return "\n\n".join(results)
# Resources

@mcp.resource("customer://{customer_id}")
def customer_resource(customer_id: str) -> str:
    """Retrieve customer information from the SQLite database."""
    customer = get_customer_from_db(int(customer_id))

    if customer is None:
        return f"Customer with ID {customer_id} was not found."

    customer_id, name, company, industry, status, last_contacted = customer

    return f"""
Customer ID: {customer_id}
Name: {name}
Company: {company}
Industry: {industry}
Status: {status}
Last Contacted: {last_contacted}
"""



#Prompt

@mcp.prompt()
def analyze_customer(customer_id: str) -> str:
    """Create a grounded analysis prompt for a customer."""

    return f"""
Analyze customer {customer_id} using ONLY information provided by
the MCP customer resource.

Important rules:

1. Do not invent or assume customer information.
2. Do not make up revenue, employee count, location, contacts,
   business problems, or other details that are not provided.
3. Clearly state when information is unavailable.
4. Base every factual statement about the customer on verified MCP data.
5. Recommendations should be practical but must be clearly identified
   as recommendations, not existing customer facts.

Provide:

1. Customer summary
2. Current customer status
3. Recent contact status
4. Potential opportunity areas based only on the available data
5. Recommended next action

Keep the analysis concise and practical.
"""

if __name__ == "__main__":
    mcp.run()