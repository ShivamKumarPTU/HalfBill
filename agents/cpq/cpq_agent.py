"""
CPQ Agent — answers questions about products, customers, and sales quotes.
"""
import httpx, sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from config import PRODUCT_API_URL
from infra.shared.llm import run_agent

BASE = f"{PRODUCT_API_URL}/cpq"

def list_products():
    return httpx.get(f"{BASE}/products", timeout=10).json()

def search_products(q: str):
    return httpx.get(f"{BASE}/products/search", params={"q": q}, timeout=10).json()

def get_product(product_id: int):
    return httpx.get(f"{BASE}/products/{product_id}", timeout=10).json()

def search_customers(name: str):
    return httpx.get(f"{BASE}/customers/search", params={"name": name}, timeout=10).json()

def get_customer(customer_id: int):
    return httpx.get(f"{BASE}/customers/{customer_id}", timeout=10).json()

def list_quotes(status: str = None, limit: int = 10):
    params = {"limit": limit}
    if status: params["status"] = status
    return httpx.get(f"{BASE}/quotes", params=params, timeout=10).json()

def get_quote(quote_number: str):
    return httpx.get(f"{BASE}/quotes/{quote_number}", timeout=10).json()

def get_customer_quotes(customer_id: int):
    return httpx.get(f"{BASE}/quotes/customer/{customer_id}", timeout=10).json()

def get_cpq_metrics():
    return httpx.get(f"{BASE}/metrics", timeout=10).json()

TOOLS = [
    {"type": "function", "function": {
        "name": "list_products",
        "description": "List all active telecom products (internet, mobile, OTT, equipment).",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "search_products",
        "description": "Search products by name or description keyword.",
        "parameters": {"type": "object", "properties": {
            "q": {"type": "string", "description": "Search keyword e.g. 'fiber', 'mobile', 'streaming'"}},
            "required": ["q"]}}},
    {"type": "function", "function": {
        "name": "get_product",
        "description": "Get full details of one product by its numeric ID.",
        "parameters": {"type": "object", "properties": {
            "product_id": {"type": "integer"}}, "required": ["product_id"]}}},
    {"type": "function", "function": {
        "name": "search_customers",
        "description": "Find customers by name (partial match).",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string"}}, "required": ["name"]}}},
    {"type": "function", "function": {
        "name": "get_customer",
        "description": "Get full profile of one customer by numeric ID.",
        "parameters": {"type": "object", "properties": {
            "customer_id": {"type": "integer"}}, "required": ["customer_id"]}}},
    {"type": "function", "function": {
        "name": "list_quotes",
        "description": "List sales quotes. Filter by status: draft, presented, accepted, rejected, expired.",
        "parameters": {"type": "object", "properties": {
            "status": {"type": "string"},
            "limit": {"type": "integer"}}}}},
    {"type": "function", "function": {
        "name": "get_quote",
        "description": "Get full quote details including all line items by quote number (e.g. QT-2024-00001).",
        "parameters": {"type": "object", "properties": {
            "quote_number": {"type": "string"}}, "required": ["quote_number"]}}},
    {"type": "function", "function": {
        "name": "get_customer_quotes",
        "description": "Get all quotes for a specific customer by numeric customer ID.",
        "parameters": {"type": "object", "properties": {
            "customer_id": {"type": "integer"}}, "required": ["customer_id"]}}},
    {"type": "function", "function": {
        "name": "get_cpq_metrics",
        "description": "Get CPQ KPIs: quotes created today, acceptance rate, MRR pipeline, average quote value.",
        "parameters": {"type": "object", "properties": {}}}},
]

TOOL_FUNCTIONS = {
    "list_products": list_products, "search_products": search_products,
    "get_product": get_product, "search_customers": search_customers,
    "get_customer": get_customer, "list_quotes": list_quotes,
    "get_quote": get_quote, "get_customer_quotes": get_customer_quotes,
    "get_cpq_metrics": get_cpq_metrics,
}

SYSTEM_PROMPT = """You are the CPQ Agent for HalfBill, a telecom revenue operations platform.
You help with product catalog queries, customer lookups, and sales quote management.

Business rules:
- Maximum discount on any quote is 30% (business rule — never suggest more)
- Quotes are valid for 30 days from creation
- Tax is always 8.5% and is added on top of the quote total at invoice stage
- MRR (Monthly Recurring Revenue) = recurring products; OTC = one-time charges

Always mention specific product names, prices, and quote numbers in your answers.
"""

def chat(query: str) -> str:
    return run_agent(SYSTEM_PROMPT, query, TOOLS, TOOL_FUNCTIONS)
