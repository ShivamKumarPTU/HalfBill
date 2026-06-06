"""
agent_registry.py — maps agent names to their MCP server URLs and descriptions.
The orchestrator uses this to know where each agent lives.
"""

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))
from config import CPQ_MCP_URL, BILLING_MCP_URL, SERVICEDESK_MCP_URL, FSM_MCP_URL

AGENTS = {
    "cpq": {
        "name": "CPQ Agent",
        "label": "[CPQ Agent]",
        "description": (
            "Handles product configuration, pricing, and quote generation. "
            "Use for: creating quotes, searching products, applying discounts, "
            "checking quote status, customer lookup, MRR pipeline."
        ),
        "url": CPQ_MCP_URL,       # http://localhost:18003
    },
    "billing": {
        "name": "Billing Agent",
        "label": "[Billing Agent]",
        "description": (
            "Handles invoices, billing anomalies, payments, and revenue leakage. "
            "Use for: invoice status, overdue accounts, payment history, "
            "anomaly detection and investigation."
        ),
        "url": BILLING_MCP_URL,   # http://localhost:18004
    },
    "servicedesk": {
        "name": "ServiceDesk Agent",
        "label": "[ServiceDesk Agent]",
        "description": (
            "Handles support tickets — creation, triage, status, resolution. "
            "Use for: opening tickets, checking status, adding comments, "
            "escalating issues, finding similar past tickets."
        ),
        "url": SERVICEDESK_MCP_URL,  # http://localhost:18005
    },
    "fsm": {
        "name": "FSM Agent",
        "label": "[FSM Agent]",
        "description": (
            "Handles field service — technician dispatch, job scheduling, status. "
            "Use for: scheduling installations or repairs, finding available "
            "technicians, updating job status."
        ),
        "url": FSM_MCP_URL,       # http://localhost:18006
    },
}
