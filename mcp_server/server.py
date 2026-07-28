from mcp.server.fastmcp import FastMCP
import os

print("Starting Enterprise MCP Server...")

mcp = FastMCP("EnterpriseAI")

DOCUMENT_FOLDER = "documents"


@mcp.tool()
def search_documents(query: str) -> str:
    """Search company documents."""

    print(f"Searching documents for: {query}")

    results = []

    for file in os.listdir(DOCUMENT_FOLDER):

        path = os.path.join(DOCUMENT_FOLDER, file)

        with open(path, "r", encoding="utf-8") as f:

            content = f.read()

            if query.lower() in content.lower():

                results.append(
                    f"FOUND IN: {file}\n\n{content[:500]}"
                )

    if not results:
        return "No matching documents found."

    return "\n\n----------------\n\n".join(results)


@mcp.tool()
def invoice_lookup(invoice_number: str) -> str:
    """Lookup invoice status."""

    print(f"Looking up invoice: {invoice_number}")

    if invoice_number == "INV-2026-001":
        return "Invoice is pending. Amount: 24,000 EUR."

    return "Invoice not found."


if __name__ == "__main__":

    print("MCP Server is running...")
    print("Waiting for MCP client connections...")

    mcp.run()