"""
Billing Agent — answers questions about invoices, payments, and revenue anomalies.
Calls the /billing/* REST endpoints and uses Groq to reason over results.
"""

import httpx
import sys, os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from config import PRODUCT_API_URL
from infra.shared.llm import run_agent

BASE = f"{PRODUCT_API_URL}/billing"

# ── Tool implementations (call the FastAPI endpoints) ─────────────────

def list_invoices(status: str = None, limit: int = 10):
    params = {"limit": limit}
    if status:
        params["status"] = status
    r = httpx.get(f"{BASE}/invoices", params=params, timeout=10)
    return r.json()

def get_invoice(invoice_number: str):
    r = httpx.get(f"{BASE}/invoices/{invoice_number}", timeout=10)
    return r.json()

def get_overdue_invoices():
    r = httpx.get(f"{BASE}/invoices/overdue", timeout=10)
    return r.json()

def get_customer_invoices(customer_id: int):
    r = httpx.get(f"{BASE}/invoices/customer/{customer_id}", timeout=10)
    return r.json()

def get_open_anomalies():
    r = httpx.get(f"{BASE}/anomalies/open", timeout=10)
    return r.json()

def get_anomalies(status: str = None, severity: str = None):
    params = {}
    if status: params["status"] = status
    if severity: params["severity"] = severity
    r = httpx.get(f"{BASE}/anomalies", params=params, timeout=10)
    return r.json()

def get_billing_metrics():
    r = httpx.get(f"{BASE}/metrics", timeout=10)
    return r.json()

def get_invoice_payments(invoice_number: str):
    r = httpx.get(f"{BASE}/payments/invoice/{invoice_number}", timeout=10)
    return r.json()

# ── Tool schemas (what Groq sees) ─────────────────────────────────────

TOOLS = [
    {"type":"function","function":{"name":"list_invoices","description":"List invoices. Optional status filter: draft/issued/paid/overdue/disputed/written_off. Optional limit.","parameters":{"type":"object","properties":{"status":{"type":"string"},"limit":{"type":"integer"}}}}},
    {"type":"function","function":{"name":"get_invoice","description":"Get full invoice by invoice_number e.g. INV-2024-00001.","parameters":{"type":"object","properties":{"invoice_number":{"type":"string"}},"required":["invoice_number"]}}},
    {"type":"function","function":{"name":"get_overdue_invoices","description":"Get all overdue invoices oldest first.","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"get_customer_invoices","description":"Get invoices for a customer by numeric customer_id.","parameters":{"type":"object","properties":{"customer_id":{"type":"integer"}},"required":["customer_id"]}}},
    {"type":"function","function":{"name":"get_open_anomalies","description":"Get all open billing anomalies sorted by severity.","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"get_billing_metrics","description":"Get billing KPIs: overdue count, revenue collected, open anomalies, leakage amount.","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"get_invoice_payments","description":"Get payment history for an invoice by invoice_number.","parameters":{"type":"object","properties":{"invoice_number":{"type":"string"}},"required":["invoice_number"]}}},
]

TOOL_FUNCTIONS = {
    "list_invoices": list_invoices,
    "get_invoice": get_invoice,
    "get_overdue_invoices": get_overdue_invoices,
    "get_customer_invoices": get_customer_invoices,
    "get_open_anomalies": get_open_anomalies,
    "get_anomalies": get_anomalies,
    "get_billing_metrics": get_billing_metrics,
    "get_invoice_payments": get_invoice_payments,
}

SYSTEM_PROMPT = """You are the Billing Agent for HalfBill (telecom revenue ops).
Answer questions about invoices, payments, and anomalies using your tools.
Rules: 8.5% tax, 30-day payment window. Always include invoice numbers and customer names."""

def chat(query: str) -> str:
    """Entry point: send a natural language query to the Billing Agent."""
    return run_agent(
        system_prompt=SYSTEM_PROMPT,
        user_query=query,
        tools=TOOLS,
        tool_functions=TOOL_FUNCTIONS,
    )


if __name__ == "__main__":
    # Quick local test
    questions = [
        "How many overdue invoices do we have and what is the total outstanding balance?",
        "Show me the open billing anomalies by severity",
        "What are our billing metrics right now?",
    ]
    for q in questions:
        print(f"\n{'='*60}\nQ: {q}\n{'='*60}")
        print(chat(q))
