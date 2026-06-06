"""CPQ MCP Server — port 18003"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

from agents.cpq.cpq_agent import chat as cpq_chat, TOOLS
from mcp_servers.base_mcp import create_mcp_app

app = create_mcp_app("CPQ Agent", cpq_chat, TOOLS, 18003)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=18003)
