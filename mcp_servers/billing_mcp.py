"""Billing MCP Server — port 18004"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

from agents.billing.billing_agent import chat as billing_chat, TOOLS
from mcp_servers.base_mcp import create_mcp_app

app = create_mcp_app("Billing Agent", billing_chat, TOOLS, 18004)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=18004)
