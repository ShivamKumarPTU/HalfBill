import os
from dotenv import load_dotenv

# Load secrets from .env file (local dev) — never hardcoded here
load_dotenv()

# --- DATABASE CONFIG ---
DB_URL = os.getenv("DB_URL")
if not DB_URL:
    raise EnvironmentError("DB_URL is not set. Copy .env.example to .env and fill it in.")

# --- GROQ API CONFIG ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise EnvironmentError("GROQ_API_KEY is not set. Copy .env.example to .env and fill it in.")

GROQ_MODEL = "llama-3.3-70b-versatile"

# --- PORT MAPPINGS ---
# Shifted to the 18000 range to keep this project completely isolated
PRODUCT_API_PORT      = 18001
ORCHESTRATOR_MCP_PORT = 18002
CPQ_MCP_PORT          = 18003
BILLING_MCP_PORT      = 18004
SERVICEDESK_MCP_PORT  = 18005
FSM_MCP_PORT          = 18006
HUB_PORT              = 18501

# --- SERVICE URLS ---
PRODUCT_API_URL      = f"http://localhost:{PRODUCT_API_PORT}"
ORCHESTRATOR_MCP_URL = f"http://localhost:{ORCHESTRATOR_MCP_PORT}"
CPQ_MCP_URL          = f"http://localhost:{CPQ_MCP_PORT}"
BILLING_MCP_URL      = f"http://localhost:{BILLING_MCP_PORT}"
SERVICEDESK_MCP_URL  = f"http://localhost:{SERVICEDESK_MCP_PORT}"
FSM_MCP_URL          = f"http://localhost:{FSM_MCP_PORT}"
