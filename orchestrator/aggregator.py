"""
aggregator.py — synthesises multiple agent responses into one coherent answer.
Called when the orchestrator runs 2+ agents for a single query.
"""

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))
from infra.shared.llm import get_client
from config import GROQ_MODEL

AGGREGATOR_PROMPT = """You are an executive assistant synthesising answers from multiple specialised AI agents.
You receive the original user query and answers from 2-4 domain agents.
Your job: write ONE clear, coherent, actionable response that combines all information.

Rules:
- Do NOT repeat agent labels or say "According to Agent X"
- Integrate the information naturally — it should read as one unified answer
- Highlight anything urgent or requiring immediate action first
- Be concise: no fluff, just the facts and recommendations
- If agents' data is related (e.g. same customer), show the connection explicitly"""


def aggregate(query: str, agent_responses: list[tuple[str, str]]) -> str:
    """
    agent_responses: list of (agent_label, response_text) tuples
    Returns: synthesised string
    """
    if len(agent_responses) == 1:
        return agent_responses[0][1]

    client = get_client()

    context_parts = []
    for label, response in agent_responses:
        context_parts.append(f"[{label}]\n{response}")
    context = "\n\n".join(context_parts)

    messages = [
        {"role": "system", "content": AGGREGATOR_PROMPT},
        {"role": "user", "content": (
            f"Original query: {query}\n\n"
            f"Agent responses:\n{context}\n\n"
            "Synthesise these into one unified answer."
        )},
    ]

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        max_tokens=800,
        temperature=0.2,
    )
    return response.choices[0].message.content.strip()
