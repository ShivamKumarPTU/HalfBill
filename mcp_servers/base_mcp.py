"""
Base MCP server factory.
Each domain MCP server is a thin FastAPI wrapper around its agent chat() function.
Exposes:
  GET  /sse        — health probe (Hub checks this)
  GET  /health     — detailed health
  POST /query      — natural language query → agent response
  GET  /tools      — list of available tools this agent exposes
"""

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Callable
import json


class QueryRequest(BaseModel):
    query: str
    context: str = ""   # optional upstream agent context (for sequential chains)


def create_mcp_app(agent_name: str, agent_chat_fn: Callable, tools: list, port: int) -> FastAPI:
    """
    Factory that creates a FastAPI MCP server for any domain agent.
    """
    app = FastAPI(
        title=f"HalfBill — {agent_name} MCP Server",
        description=f"MCP server for the {agent_name}. Exposes agent tools over HTTP.",
        version="1.0.0",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
    )

    @app.get("/sse", summary="SSE health probe")
    async def sse_health():
        """
        Server-Sent Events health endpoint.
        The Hub checks this to show agent Online/Offline status.
        Returns an SSE stream that immediately closes with a 'connected' event.
        """
        async def event_stream():
            yield "data: {\"event\": \"connected\", \"agent\": \"" + agent_name + "\"}\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    @app.get("/health", summary="Detailed health check")
    async def health():
        return {
            "status": "ok",
            "agent": agent_name,
            "port": port,
            "tools_count": len(tools),
        }

    @app.post("/query", summary="Natural language query to this agent")
    async def query_agent(body: QueryRequest):
        """
        Send a natural language question to this agent.
        The agent calls the relevant FastAPI REST endpoints,
        reasons with Groq LLM, and returns a structured answer.
        """
        full_query = (
            f"Context from previous agents:\n{body.context}\n\nQuery: {body.query}"
            if body.context else body.query
        )
        try:
            import asyncio
            response = await asyncio.to_thread(agent_chat_fn, full_query)
            return {"agent": agent_name, "response": response, "status": "ok"}
        except Exception as e:
            return {"agent": agent_name, "response": f"Error: {str(e)}", "status": "error"}

    @app.get("/tools", summary="List available tools")
    async def list_tools():
        return {
            "agent": agent_name,
            "tools": [
                {"name": t["function"]["name"], "description": t["function"]["description"]}
                for t in tools
            ]
        }

    return app
