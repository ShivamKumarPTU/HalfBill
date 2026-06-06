"""
router.py — LLM-based multi-agent router.
Returns a list of agents to call + execution mode.

Modes:
  parallel   — call all agents simultaneously (asyncio.gather)
  sequential — chain agents, pass output of one as context to next
"""

import json, sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))
from infra.shared.llm import get_client
from config import GROQ_MODEL

AGENT_DESCRIPTIONS = {
    "cpq":          "Products, pricing, quotes, discounts, customers, MRR pipeline",
    "billing":      "Invoices, payments, overdue accounts, revenue anomalies, leakage",
    "servicedesk":  "Support tickets, complaints, escalations, ticket status, triage",
    "fsm":          "Field technicians, job dispatch, installations, repairs, scheduling",
}

ROUTING_PROMPT = """You are an intent classifier for a telecom revenue ops platform.
Given a user query, return a JSON object identifying which agents are needed and how to run them.

Available agents:
- cpq: Products, pricing, quotes, discounts, customers, MRR pipeline
- billing: Invoices, payments, overdue accounts, revenue anomalies, leakage  
- servicedesk: Support tickets, complaints, escalations, ticket status
- fsm: Field technicians, job dispatch, installations, repairs, scheduling

Return ONLY valid JSON in this exact format:
{
  "agents": ["agent1", "agent2"],
  "mode": "parallel" | "sequential",
  "reason": "brief explanation"
}

Rules:
- "parallel" when agents are INDEPENDENT (e.g. billing + servicedesk for different questions)
- "sequential" when agents DEPEND ON EACH OTHER (e.g. cpq→billing→fsm for Q2C2C flow)
- For sequential, list agents in dependency order (first agent output feeds into second)
- Never include an agent if the query doesn't need it
- Always return valid JSON. No markdown, no explanation, just JSON."""


def route(query: str) -> dict:
    """
    Returns:
    {
        "agents": ["billing", "servicedesk"],
        "mode": "parallel" | "sequential",
        "reason": str
    }
    """
    client = get_client()
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": ROUTING_PROMPT},
            {"role": "user", "content": query},
        ],
        max_tokens=200,
        temperature=0.0,
    )
    raw = response.choices[0].message.content.strip()

    # Strip markdown fences if model adds them
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    try:
        result = json.loads(raw)
        # Validate agent names
        valid_agents = [a for a in result.get("agents", []) if a in AGENT_DESCRIPTIONS]
        result["agents"] = valid_agents if valid_agents else ["billing"]
        result.setdefault("mode", "parallel")
        result.setdefault("reason", "")
        return result
    except json.JSONDecodeError:
        # Fallback: keyword detection
        q = query.lower()
        agents = []
        if any(w in q for w in ["invoice","payment","overdue","anomaly","leakage","billing","revenue"]):
            agents.append("billing")
        if any(w in q for w in ["quote","product","price","discount","customer","fiber","mobile"]):
            agents.append("cpq")
        if any(w in q for w in ["ticket","support","complaint","escalate","issue"]):
            agents.append("servicedesk")
        if any(w in q for w in ["technician","job","dispatch","install","repair","schedule","zone"]):
            agents.append("fsm")
        return {"agents": agents or ["billing"], "mode": "parallel", "reason": "fallback keyword routing"}
