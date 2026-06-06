"""ServiceDesk MCP Server — port 18005"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

from agents.servicedesk.sd_agent import chat as sd_chat, TOOLS
from mcp_servers.base_mcp import create_mcp_app

app = create_mcp_app("ServiceDesk Agent", sd_chat, TOOLS, 18005)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=18005)
