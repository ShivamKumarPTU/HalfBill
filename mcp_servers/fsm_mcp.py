"""FSM MCP Server — port 18006"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

from agents.fsm.fsm_agent import chat as fsm_chat, TOOLS
from mcp_servers.base_mcp import create_mcp_app

app = create_mcp_app("FSM Agent", fsm_chat, TOOLS, 18006)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=18006)
