"""
Orchestrator MCP Server — port 18002
Master entry point for all external MCP clients (Claude Desktop, Cursor, etc.)
Exposes a single /query endpoint that runs the full multi-agent pipeline.
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

app = FastAPI(
    title="HalfBill — Orchestrator MCP Server",
    description="Master orchestrator. Routes queries to CPQ, Billing, ServiceDesk, or FSM agents.",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


class QueryRequest(BaseModel):
    query: str


@app.get("/sse", summary="SSE health probe")
async def sse_health():
    async def event_stream():
        yield 'data: {"event": "connected", "agent": "Orchestrator"}\n\n'
    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/health")
async def health():
    return {"status": "ok", "agent": "Orchestrator", "port": 18002}


@app.post("/query", summary="Multi-agent query via orchestrator")
async def query(body: QueryRequest):
    """
    Full multi-agent pipeline:
    1. Router LLM → identifies agents + mode
    2. Execute agents (parallel or sequential)
    3. Aggregator LLM → synthesises if multiple agents
    """
    try:
        import asyncio
        from orchestrator import route_and_respond
        result = await asyncio.to_thread(route_and_respond, body.query)
        return {
            "status": "ok",
            "agents_used": result["agents_used"],
            "mode": result["mode"],
            "routing_reason": result["routing_reason"],
            "response": result["response"],
            "agent_responses": result["agent_responses"],
        }
    except Exception as e:
        return {"status": "error", "response": str(e)}


@app.get("/agents", summary="List registered agents")
async def list_agents():
    from infra.shared.agent_registry import AGENTS
    return {
        domain: {
            "name": info["name"],
            "url": info["url"],
            "description": info["description"],
        }
        for domain, info in AGENTS.items()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=18002)
