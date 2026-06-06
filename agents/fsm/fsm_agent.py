"""FSM Agent — technician availability, job status, and field dispatch."""
import httpx, sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from config import PRODUCT_API_URL
from infra.shared.llm import run_agent

BASE = f"{PRODUCT_API_URL}/fsm"

def list_technicians():
    return httpx.get(f"{BASE}/technicians", timeout=10).json()

def get_available_technicians(zone: str = None, specialization: str = None):
    params = {}
    if zone: params["zone"] = zone
    if specialization: params["specialization"] = specialization
    return httpx.get(f"{BASE}/technicians/available", params=params, timeout=10).json()

def get_technician(technician_id: int):
    return httpx.get(f"{BASE}/technicians/{technician_id}", timeout=10).json()

def get_technician_schedule(technician_id: int):
    return httpx.get(f"{BASE}/technicians/{technician_id}/schedule", timeout=10).json()

def list_jobs(status: str = None, priority: str = None, limit: int = 10):
    params = {"limit": limit}
    if status: params["status"] = status
    if priority: params["priority"] = priority
    return httpx.get(f"{BASE}/jobs", params=params, timeout=10).json()

def get_pending_jobs():
    return httpx.get(f"{BASE}/jobs/pending", timeout=10).json()

def get_job(job_number: str):
    return httpx.get(f"{BASE}/jobs/{job_number}", timeout=10).json()

def get_customer_jobs(customer_id: int):
    return httpx.get(f"{BASE}/jobs/customer/{customer_id}", timeout=10).json()

def get_fsm_metrics():
    return httpx.get(f"{BASE}/metrics", timeout=10).json()

TOOLS = [
    {"type": "function", "function": {
        "name": "list_technicians",
        "description": "List all 25 field technicians with their zone, specializations, status, and rating.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "get_available_technicians",
        "description": "Find available technicians, optionally filtered by zone (North/South/East/West/Central) or specialization (fiber/mobile/equipment/installation).",
        "parameters": {"type": "object", "properties": {
            "zone": {"type": "string"},
            "specialization": {"type": "string"}}}}},
    {"type": "function", "function": {
        "name": "get_technician",
        "description": "Get profile of one technician by numeric ID.",
        "parameters": {"type": "object", "properties": {
            "technician_id": {"type": "integer"}}, "required": ["technician_id"]}}},
    {"type": "function", "function": {
        "name": "get_technician_schedule",
        "description": "Get availability schedule for a technician for the next 14 days.",
        "parameters": {"type": "object", "properties": {
            "technician_id": {"type": "integer"}}, "required": ["technician_id"]}}},
    {"type": "function", "function": {
        "name": "list_jobs",
        "description": "List field service jobs with optional status or priority filter.",
        "parameters": {"type": "object", "properties": {
            "status": {"type": "string", "description": "pending, assigned, en_route, in_progress, completed, cancelled"},
            "priority": {"type": "string", "description": "low, medium, high, emergency"},
            "limit": {"type": "integer"}}}}},
    {"type": "function", "function": {
        "name": "get_pending_jobs",
        "description": "Get all unassigned pending jobs sorted by priority (emergency first).",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "get_job",
        "description": "Get full job details including technician assignment by job number (e.g. JOB-2026-0001).",
        "parameters": {"type": "object", "properties": {
            "job_number": {"type": "string"}}, "required": ["job_number"]}}},
    {"type": "function", "function": {
        "name": "get_customer_jobs",
        "description": "Get all field service jobs for a specific customer by numeric customer ID.",
        "parameters": {"type": "object", "properties": {
            "customer_id": {"type": "integer"}}, "required": ["customer_id"]}}},
    {"type": "function", "function": {
        "name": "get_fsm_metrics",
        "description": "Get FSM KPIs: jobs scheduled today, completed, in-progress, pending, technician utilisation %.",
        "parameters": {"type": "object", "properties": {}}}},
]

TOOL_FUNCTIONS = {
    "list_technicians": list_technicians,
    "get_available_technicians": get_available_technicians,
    "get_technician": get_technician,
    "get_technician_schedule": get_technician_schedule,
    "list_jobs": list_jobs,
    "get_pending_jobs": get_pending_jobs,
    "get_job": get_job,
    "get_customer_jobs": get_customer_jobs,
    "get_fsm_metrics": get_fsm_metrics,
}

SYSTEM_PROMPT = """You are the FSM (Field Service Management) Agent for HalfBill, a telecom platform.
You handle technician availability, job dispatch, and field service operations.

Guidelines:
- Emergency priority jobs must be assigned within 2 hours
- Always check technician availability and zone before suggesting assignment
- Technicians must have the right specialization for the job type
- A technician with status 'on_job' cannot be assigned to another job
- Always provide technician names, zones, and ratings when making recommendations
"""

def chat(query: str) -> str:
    return run_agent(SYSTEM_PROMPT, query, TOOLS, TOOL_FUNCTIONS)
