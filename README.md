# HalfBill — Autonomous AI Revenue Operations Platform

> An end-to-end, multi-agent AI system that automates the complete telecom revenue cycle.  
> Quote → Bill → Support → Dispatch. Powered by natural language.

---

## What Is This?

HalfBill is a **production-grade, multi-agent AI platform** built on the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/). It replaces manual revenue operations workflows with a network of autonomous AI agents — each specialised in a business domain — that can work independently, in parallel, or in sequence to answer complex cross-domain queries.

**Ask it anything:**
- *"Which customers have overdue invoices AND open support tickets?"*
- *"Create a fiber internet quote for ACME Corp, then generate the invoice"*
- *"Find available technicians in the North zone and schedule a new job"*

---

## Architecture

```
User (Natural Language)
        │
        ▼
┌───────────────────────┐
│   Orchestrator MCP    │  ← Smart LLM router (port 18002)
│   (orchestrator.py)   │    Decides: single / parallel / sequential
└───────┬───────────────┘
        │
   ┌────┴────────────────────────────────┐
   │    PARALLEL (asyncio.gather)        │
   ▼                                     ▼
┌──────────┐  ┌──────────┐  ┌─────────────┐  ┌──────────┐
│ CPQ MCP  │  │Billing   │  │ServiceDesk  │  │ FSM MCP  │
│ :18003   │  │MCP :18004│  │MCP   :18005 │  │ :18006   │
└────┬─────┘  └────┬─────┘  └──────┬──────┘  └────┬─────┘
     │              │               │               │
     └──────────────┴───────────────┴───────────────┘
                            │
                    Aggregator LLM
                    (unified answer)
                            │
                            ▼
                ┌───────────────────────┐
                │  FastAPI REST API     │  ← Business logic (port 18001)
                │  (fastapi_app/)       │
                └──────────┬────────────┘
                           │
                ┌──────────▼────────────┐
                │  PostgreSQL + pgvector │  ← Docker (port 15432)
                │  17 tables, 1000+rows  │
                └───────────────────────┘
```

### Execution Modes

| Mode | When | Example |
|------|------|---------|
| **Single** | Query targets one domain | *"Show overdue invoices"* |
| **Parallel** | Query spans 2+ independent domains | *"Customer has overdue invoice AND open ticket"* |
| **Sequential** | Output of one agent feeds the next | *"Create quote → generate invoice → dispatch tech"* |

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| AI / LLM | [Groq](https://groq.com/) — LLaMA 3.3 70B Versatile |
| Agent Protocol | [MCP](https://modelcontextprotocol.io/) via FastAPI SSE |
| Backend API | Python · FastAPI · Uvicorn |
| Database | PostgreSQL 15 + pgvector (Docker) |
| Dashboard | Streamlit |
| Async Orchestration | `asyncio.gather()` · `asyncio.to_thread()` |
| Runtime | Python 3.13 · Windows / Linux |

---

## Project Structure

```
shivam_halfbill_project/
│
├── config.py                    # All ports, keys, and service URLs
│
├── fastapi_app/                 # Core REST API
│   ├── main.py                  # FastAPI app — mounts all routers
│   ├── models.py                # Shared Pydantic schemas
│   └── routers/
│       ├── cpq.py               # Configure · Price · Quote endpoints
│       ├── billing.py           # Invoice · Payment · Anomaly endpoints
│       ├── servicedesk.py       # Ticket · Category · Comment endpoints
│       └── fsm.py               # Technician · Job · Schedule endpoints
│
├── agents/                      # AI agents (Groq tool-use loop)
│   ├── billing/billing_agent.py
│   ├── cpq/cpq_agent.py
│   ├── servicedesk/sd_agent.py
│   └── fsm/fsm_agent.py
│
├── orchestrator/                # Multi-agent coordination
│   ├── router.py                # LLM-based query router
│   ├── aggregator.py            # Multi-agent response synthesiser
│   └── orchestrator_server.py  # Master MCP server (port 18002)
│
├── mcp_servers/                 # Domain MCP servers
│   ├── base_mcp.py              # Shared MCP server factory
│   ├── billing_mcp.py           # port 18004
│   ├── cpq_mcp.py               # port 18003
│   ├── sd_mcp.py                # port 18005
│   └── fsm_mcp.py               # port 18006
│
├── infra/shared/                # Shared infrastructure
│   ├── db.py                    # Async PostgreSQL connection pool
│   ├── llm.py                   # Groq tool-use agentic loop
│   └── agent_registry.py        # Agent URL + description registry
│
├── hub.py                       # Streamlit dashboard (port 18501)
├── orchestrator.py              # Orchestrator entry point
├── start_all.py                 # One command to launch everything
└── requirements.txt
```

---

## Prerequisites

| Requirement | Version |
|-------------|---------|
| Python | 3.10+ |
| Docker Desktop | Latest |
| Groq API Key | Free tier at [console.groq.com](https://console.groq.com) |

---

## Setup & Installation

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd shivam_halfbill_project
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 3. Start the Database (Docker)

```bash
# First time only — pulls and starts the PostgreSQL + pgvector container
docker run --name my_halfbill_db \
  -e POSTGRES_PASSWORD=secret \
  -p 15432:5432 \
  -d pgvector/pgvector:pg15

# Load the schema and seed data
docker exec -i my_halfbill_db psql -U postgres < ../internship_2026_study_material/complete_setup.sql

# Fix missing FSM seed data
python fix_fsm_data.py
```

> **Subsequent starts** (after PC restart):
> ```bash
> docker start my_halfbill_db
> ```

### 4. Configure Your API Key

Open `config.py` and set your Groq key:

```python
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "your_groq_key_here")
```

Or set it as an environment variable:

```bash
# Windows PowerShell
$env:GROQ_API_KEY = "your_groq_key_here"
```

### 5. Launch All Services

```bash
python start_all.py
```

This starts all **7 services** with staggered startup:

| Service | URL |
|---------|-----|
| FastAPI REST API | http://localhost:18001/docs |
| Orchestrator MCP | http://localhost:18002/health |
| CPQ MCP | http://localhost:18003/health |
| Billing MCP | http://localhost:18004/health |
| ServiceDesk MCP | http://localhost:18005/health |
| FSM MCP | http://localhost:18006/health |
| Streamlit Hub | http://localhost:18501 |

---

## Usage

### Option 1 — Streamlit Dashboard (Recommended)

Open **http://localhost:18501** in your browser.

- **Command Center** — Live KPI metrics from all 4 modules
- **AI Chat** — Natural language interface to the full multi-agent system
- **Sidebar** — Real-time health status of all 5 MCP servers

### Option 2 — Direct API (Swagger UI)

Open **http://localhost:18001/docs** to explore and test all REST endpoints interactively.

### Option 3 — Python (Direct Agent Call)

```python
import sys
sys.path.insert(0, '.')

from orchestrator import route_and_respond

# Single agent
answer = route_and_respond("How many overdue invoices do we have?")

# Triggers parallel agents automatically
answer = route_and_respond("Show customers with overdue invoices AND open support tickets")

# Triggers sequential chain (Quote → Invoice → Dispatch)
answer = route_and_respond("Create a fiber quote for customer CUST-001 then generate the invoice")

print(answer)
```

### Option 4 — MCP Client (Claude Desktop / Cursor)

Add this to your Claude Desktop config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "halfbill": {
      "url": "http://localhost:18002/sse"
    }
  }
}
```

---

## API Reference (Quick)

### CPQ — `/cpq/`
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/cpq/products/search?q=fiber` | Search products |
| `GET` | `/cpq/customers` | List all customers |
| `POST` | `/cpq/quotes` | Create a quote (30% discount cap enforced) |
| `GET` | `/cpq/metrics` | Pipeline metrics & MRR |

### Billing — `/billing/`
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/billing/invoices` | List invoices (filter by status) |
| `GET` | `/billing/invoices/overdue` | All overdue invoices |
| `POST` | `/billing/payments` | Record a payment |
| `GET` | `/billing/anomalies/open` | Revenue leakage anomalies |
| `GET` | `/billing/metrics` | Revenue metrics |

### ServiceDesk — `/servicedesk/`
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/servicedesk/tickets` | List tickets |
| `POST` | `/servicedesk/tickets` | Create a ticket |
| `PATCH` | `/servicedesk/tickets/{id}/status` | Update ticket status |
| `GET` | `/servicedesk/metrics` | SLA & ticket metrics |

### FSM — `/fsm/`
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/fsm/technicians/available` | Available technicians |
| `POST` | `/fsm/jobs` | Create a field job |
| `PATCH` | `/fsm/jobs/{id}/assign` | Assign technician to job |
| `GET` | `/fsm/metrics` | Utilisation metrics |

---

## Live Data (Seed Database)

| Domain | Records |
|--------|---------|
| Customers | 1,000 |
| Products | 15 |
| Quotes | 350 |
| Invoices | ~500 |
| Support Tickets | 400 |
| Technicians | 25 |
| Field Jobs | ~200 |

---

## Running Tests

```bash
# Test the multi-agent router logic
python test_router.py

# Test a live agent query
python quick_test.py

# Full end-to-end agent test (all 4 agents)
python test_agents.py
```

---

## Key Design Decisions

**Why MCP over direct function calls?**  
MCP makes each agent a standard HTTP service. Any MCP-compatible client (Claude Desktop, Cursor, n8n, custom tooling) can connect to the Orchestrator and use the full platform — no SDK required.

**Why Groq over Ollama (local)?**  
LLaMA 3.3 70B on Groq's free tier gives better reasoning than Mistral 7B locally, without the 5-6GB RAM cost on your machine.

**Why `asyncio.gather()` for parallel agents?**  
Cross-domain queries (e.g. billing + service desk) have zero data dependency — running them in parallel halves response time vs. sequential calls.

---

## Roadmap

- [ ] Persistent conversation history (Redis / SQLite)
- [ ] Auth layer for MCP endpoints (API keys)
- [ ] Webhook support (e.g. auto-escalate overdue invoices)
- [ ] Cross-referencing queries (3-way join across agents)
- [ ] Deploy to Railway / Render for cloud access

---

## Built By

**Shivam Kumar** — Platform Architecture, AI Engineering, Full-Stack  
Internship Project · OneBill · 2026

---

## License

MIT — use it, fork it, ship it.
