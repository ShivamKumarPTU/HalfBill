"""ServiceDesk Agent — ticket lookup, triage, and support operations."""
import httpx, sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from config import PRODUCT_API_URL
from infra.shared.llm import run_agent

BASE = f"{PRODUCT_API_URL}/servicedesk"

def list_open_tickets():
    return httpx.get(f"{BASE}/tickets/open", timeout=10).json()

def list_tickets(status: str = None, priority: str = None, limit: int = 10):
    params = {"limit": limit}
    if status: params["status"] = status
    if priority: params["priority"] = priority
    return httpx.get(f"{BASE}/tickets", params=params, timeout=10).json()

def get_ticket(ticket_number: str):
    return httpx.get(f"{BASE}/tickets/{ticket_number}", timeout=10).json()

def get_customer_tickets(customer_id: int):
    return httpx.get(f"{BASE}/tickets/customer/{customer_id}", timeout=10).json()

def list_categories():
    return httpx.get(f"{BASE}/categories", timeout=10).json()

def get_sd_metrics():
    return httpx.get(f"{BASE}/metrics", timeout=10).json()

TOOLS = [
    {"type": "function", "function": {
        "name": "list_open_tickets",
        "description": "Get all currently open and in-progress tickets, sorted by priority (critical first).",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "list_tickets",
        "description": "List tickets with optional filters by status or priority.",
        "parameters": {"type": "object", "properties": {
            "status": {"type": "string", "description": "open, in_progress, pending_customer, resolved, closed"},
            "priority": {"type": "string", "description": "low, medium, high, critical"},
            "limit": {"type": "integer"}}}}},
    {"type": "function", "function": {
        "name": "get_ticket",
        "description": "Get full ticket details including all comments by ticket number (e.g. TKT-2024-00001).",
        "parameters": {"type": "object", "properties": {
            "ticket_number": {"type": "string"}}, "required": ["ticket_number"]}}},
    {"type": "function", "function": {
        "name": "get_customer_tickets",
        "description": "Get all support tickets for a specific customer by numeric customer ID.",
        "parameters": {"type": "object", "properties": {
            "customer_id": {"type": "integer"}}, "required": ["customer_id"]}}},
    {"type": "function", "function": {
        "name": "list_categories",
        "description": "List all support ticket categories and their product areas.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "get_sd_metrics",
        "description": "Get ServiceDesk KPIs: tickets created today, resolved today, open count, critical open.",
        "parameters": {"type": "object", "properties": {}}}},
]

TOOL_FUNCTIONS = {
    "list_open_tickets": list_open_tickets, "list_tickets": list_tickets,
    "get_ticket": get_ticket, "get_customer_tickets": get_customer_tickets,
    "list_categories": list_categories, "get_sd_metrics": get_sd_metrics,
}

SYSTEM_PROMPT = """You are the ServiceDesk Agent for HalfBill, a telecom revenue operations platform.
You handle customer support ticket queries, triage, and escalations.

Guidelines:
- Critical tickets must be escalated immediately to a senior agent
- Tickets linked to billing anomalies indicate revenue impact — flag these
- Tickets requiring field visits should be checked against FSM job availability
- Always mention ticket numbers, customer names, and current status in responses
"""

def chat(query: str) -> str:
    return run_agent(SYSTEM_PROMPT, query, TOOLS, TOOL_FUNCTIONS)
