"""
orchestrator.py — HalfBill Multi-Agent Orchestrator
=====================================================

Execution Modes
---------------
PARALLEL   → Two+ independent agents run simultaneously via asyncio.gather()
             e.g. "Customer has billing issue AND open ticket"
             Billing + ServiceDesk run at the same time → Aggregator synthesises

SEQUENTIAL → Agents run in order; earlier output is fed as context to next agent
             e.g. "Create quote, generate invoice, schedule install" (Q2C2C)
             CPQ runs → result passed to Billing → result passed to FSM

SINGLE     → Only one agent needed, no aggregation
             e.g. "Show overdue invoices" → just Billing

Architecture
------------
User query
    │
    ▼
router.py (LLM) → {"agents": ["billing","servicedesk"], "mode": "parallel"}
    │
    ▼ (parallel mode)
asyncio.gather(billing.chat, servicedesk.chat)   ← both run at same time
    │               │
    ▼               ▼
billing_resp    sd_resp
    │               │
    └───────┬───────┘
            ▼
    aggregator.py (LLM) → unified answer
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from orchestrator.router import route
from orchestrator.aggregator import aggregate
from infra.shared.agent_registry import AGENTS

# Import domain agent chat functions
from agents.billing.billing_agent import chat as billing_chat
from agents.cpq.cpq_agent import chat as cpq_chat
from agents.servicedesk.sd_agent import chat as sd_chat
from agents.fsm.fsm_agent import chat as fsm_chat

AGENT_FN_MAP = {
    "billing":     billing_chat,
    "cpq":         cpq_chat,
    "servicedesk": sd_chat,
    "fsm":         fsm_chat,
}


# ── Async wrappers (sync agent functions → run in thread pool) ────────

async def run_agent_async(domain: str, query: str, context: str = "") -> tuple[str, str]:
    """
    Wraps a synchronous agent chat() call in asyncio.to_thread()
    so it can run concurrently with other agents.
    Returns (domain, response_text).
    """
    fn = AGENT_FN_MAP[domain]
    full_query = f"{context}\n\nUser query: {query}" if context else query
    response = await asyncio.to_thread(fn, full_query)
    return (domain, response)


# ── Execution modes ───────────────────────────────────────────────────

async def run_parallel(domains: list[str], query: str) -> list[tuple[str, str]]:
    """
    Run all agents simultaneously. Returns list of (domain, response).
    """
    tasks = [run_agent_async(d, query) for d in domains]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    output = []
    for domain, result in zip(domains, results):
        if isinstance(result, Exception):
            output.append((domain, f"[Agent error: {str(result)}]"))
        else:
            output.append(result)
    return output


async def run_sequential(domains: list[str], query: str) -> list[tuple[str, str]]:
    """
    Run agents in order. Each agent receives the accumulated context
    from all previous agents. Last agent's output closes the chain.
    """
    results = []
    accumulated_context = ""

    for domain in domains:
        context = (
            f"Previous steps context:\n{accumulated_context}"
            if accumulated_context else ""
        )
        domain_result, response = await run_agent_async(domain, query, context)
        results.append((domain_result, response))
        accumulated_context += f"\n[{AGENTS[domain]['name']} output]:\n{response}\n"

    return results


# ── Main orchestration entry point ────────────────────────────────────

def route_and_respond(query: str, verbose: bool = False) -> dict:
    """
    Full multi-agent pipeline:
    1. Route → identify which agents + mode
    2. Execute → parallel or sequential
    3. Aggregate → synthesise if multiple agents
    Returns dict with full trace info.
    """

    # Step 1: Route
    routing = route(query)
    domains = routing["agents"]
    mode = routing["mode"]
    reason = routing.get("reason", "")

    if verbose:
        print(f"\n[Orchestrator] Route: {domains} | Mode: {mode}")
        print(f"[Orchestrator] Reason: {reason}")

    # Step 2: Execute
    if len(domains) == 1:
        # Single agent — no need for aggregation
        agent_results = asyncio.run(run_parallel(domains, query))
        execution_mode = "single"
    elif mode == "sequential":
        agent_results = asyncio.run(run_sequential(domains, query))
        execution_mode = "sequential"
    else:
        # Parallel (default for multi-agent)
        agent_results = asyncio.run(run_parallel(domains, query))
        execution_mode = "parallel"

    if verbose:
        for domain, resp in agent_results:
            label = AGENTS[domain]["label"]
            print(f"\n{label}:\n{resp[:200]}{'...' if len(resp) > 200 else ''}")

    # Step 3: Aggregate
    labeled_results = [
        (AGENTS[d]["name"], r)
        for d, r in agent_results
    ]

    if len(labeled_results) == 1:
        final_response = labeled_results[0][1]
    else:
        if verbose:
            print(f"\n[Aggregator] Synthesising {len(labeled_results)} agent responses...")
        final_response = aggregate(query, labeled_results)

    # Build agent labels for display
    agent_labels = [AGENTS[d]["label"] for d in domains]

    return {
        "agents_used":      agent_labels,
        "domains":          domains,
        "mode":             execution_mode,
        "routing_reason":   reason,
        "agent_responses":  {d: r for d, r in agent_results},
        "response":         final_response,
    }


# ── Interactive CLI ───────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 65)
    print("  HalfBill Multi-Agent Orchestrator — CLI")
    print("  Modes: single / parallel / sequential")
    print("  Type 'exit' to quit")
    print("=" * 65)

    while True:
        query = input("\nYou: ").strip()
        if query.lower() in ("exit", "quit", "q"):
            break
        if not query:
            continue

        result = route_and_respond(query, verbose=True)

        print(f"\n{'='*65}")
        print(f"Agents: {' + '.join(result['agents_used'])}  |  Mode: {result['mode'].upper()}")
        print(f"{'='*65}")
        print(result["response"])
