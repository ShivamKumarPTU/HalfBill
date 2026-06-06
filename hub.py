"""
HalfBill Agentic Hub — Streamlit Dashboard
Live KPI metrics + AI chat powered by the Orchestrator
"""

import sys
import os
import time
import httpx
import streamlit as st

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

# ── Page config (MUST be first Streamlit call) ────────────────────────
st.set_page_config(
    page_title="HalfBill | Agentic Hub",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

from config import PRODUCT_API_URL

BASE = PRODUCT_API_URL

# ── CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
  /* ---- Global ---- */
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
  html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

  /* ---- Background ---- */
  .stApp { background: #0d1117; color: #e6edf3; }

  /* ---- Sidebar ---- */
  [data-testid="stSidebar"] {
    background: linear-gradient(180deg, #161b22 0%, #0d1117 100%);
    border-right: 1px solid #21262d;
  }

  /* ---- Metric cards ---- */
  .metric-card {
    background: linear-gradient(135deg, #161b22 0%, #1c2128 100%);
    border: 1px solid #30363d;
    border-radius: 12px;
    padding: 20px 24px;
    margin: 6px 0;
    transition: transform 0.2s ease, border-color 0.2s ease;
  }
  .metric-card:hover { transform: translateY(-2px); border-color: #58a6ff; }
  .metric-label { font-size: 12px; font-weight: 500; color: #8b949e; letter-spacing: 0.05em; text-transform: uppercase; margin-bottom: 6px; }
  .metric-value { font-size: 32px; font-weight: 700; color: #e6edf3; line-height: 1; }
  .metric-sub   { font-size: 12px; color: #8b949e; margin-top: 4px; }
  .metric-good  { color: #3fb950; }
  .metric-warn  { color: #d29922; }
  .metric-danger{ color: #f85149; }

  /* ---- Section headers ---- */
  .section-header {
    font-size: 11px; font-weight: 600; color: #8b949e;
    letter-spacing: 0.08em; text-transform: uppercase;
    border-bottom: 1px solid #21262d; padding-bottom: 8px;
    margin: 20px 0 12px 0;
  }

  /* ---- Chat messages ---- */
  .chat-user {
    background: #1f6feb22;
    border: 1px solid #1f6feb55;
    border-radius: 12px 12px 2px 12px;
    padding: 12px 16px; margin: 8px 0;
    color: #e6edf3;
  }
  .chat-agent {
    background: #1c2128;
    border: 1px solid #30363d;
    border-radius: 2px 12px 12px 12px;
    padding: 12px 16px; margin: 8px 0;
    color: #e6edf3;
  }
  .agent-badge {
    display: inline-block;
    background: #21262d;
    border: 1px solid #30363d;
    border-radius: 20px;
    padding: 2px 10px;
    font-size: 11px; font-weight: 600;
    color: #58a6ff; margin-bottom: 8px;
  }
  .routing-info {
    font-size: 10px; color: #6e7681;
    margin-top: 6px; font-style: italic;
  }

  /* ---- Status pills ---- */
  .pill-green  { background:#1a3a1e; color:#3fb950; border:1px solid #238636; border-radius:20px; padding:2px 10px; font-size:12px; font-weight:600; }
  .pill-yellow { background:#2d2a1e; color:#d29922; border:1px solid #9e6a03; border-radius:20px; padding:2px 10px; font-size:12px; font-weight:600; }
  .pill-red    { background:#3d1a1a; color:#f85149; border:1px solid #b91c1c; border-radius:20px; padding:2px 10px; font-size:12px; font-weight:600; }

  /* ---- Title ---- */
  .hub-title { font-size: 28px; font-weight: 700; color: #e6edf3; line-height: 1.2; }
  .hub-sub   { font-size: 14px; color: #8b949e; margin-top: 4px; }

  /* ---- Override Streamlit defaults ---- */
  .stTextInput > div > div > input {
    background: #161b22 !important;
    border: 1px solid #30363d !important;
    border-radius: 8px !important;
    color: #e6edf3 !important;
  }
  .stButton > button {
    background: linear-gradient(135deg, #1f6feb, #388bfd) !important;
    border: none !important; border-radius: 8px !important;
    color: white !important; font-weight: 600 !important;
    padding: 8px 20px !important;
    transition: opacity 0.2s ease !important;
  }
  .stButton > button:hover { opacity: 0.85 !important; }
  div[data-testid="stMetric"] { background: transparent; }
  .stSelectbox > div > div { background: #161b22 !important; border-color: #30363d !important; }
</style>
""", unsafe_allow_html=True)


# ── Data fetching helpers ─────────────────────────────────────────────

@st.cache_data(ttl=30)  # Cache for 30 seconds
def fetch_metrics():
    """Fetch live KPIs from all 4 modules."""
    metrics = {}
    endpoints = {
        "billing": f"{BASE}/billing/metrics",
        "cpq": f"{BASE}/cpq/metrics",
        "servicedesk": f"{BASE}/servicedesk/metrics",
        "fsm": f"{BASE}/fsm/metrics",
    }
    for module, url in endpoints.items():
        try:
            r = httpx.get(url, timeout=5)
            metrics[module] = r.json() if r.status_code == 200 else {}
        except Exception:
            metrics[module] = {}
    return metrics


def check_api_health():
    try:
        r = httpx.get(f"{BASE}/health", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def ask_agent(query: str) -> dict:
    """Route query through the orchestrator."""
    from orchestrator import route_and_respond
    return route_and_respond(query, verbose=False)


# ── Sidebar ───────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("""
    <div style="padding: 8px 0 20px 0;">
        <div style="font-size:22px; font-weight:700; color:#e6edf3;">
            ⚡ HalfBill
        </div>
        <div style="font-size:12px; color:#8b949e; margin-top:2px;">
            Agentic Revenue Ops Platform
        </div>
    </div>
    """, unsafe_allow_html=True)

    # API health check
    api_ok = check_api_health()
    status_html = (
        '<span class="pill-green">&#9679; API Live</span>'
        if api_ok else
        '<span class="pill-red">&#9679; API Down</span>'
    )
    st.markdown(status_html, unsafe_allow_html=True)
    st.markdown("---")

    page = st.radio(
        "Navigate",
        ["Command Center", "AI Chat", "About"],
        label_visibility="collapsed"
    )

    st.markdown("---")

    # MCP Server health probes
    st.markdown('<div style="font-size:11px; font-weight:600; color:#8b949e; letter-spacing:0.06em;">MCP SERVERS</div>', unsafe_allow_html=True)
    MCP_SERVERS = {
        "Orchestrator": 18002,
        "CPQ":          18003,
        "Billing":      18004,
        "ServiceDesk":  18005,
        "FSM":          18006,
    }
    for name, port in MCP_SERVERS.items():
        try:
            r = httpx.get(f"http://localhost:{port}/sse", timeout=1.5)
            ok = r.status_code == 200
        except Exception:
            ok = False
        dot = '<span style="color:#3fb950;">&#9679;</span>' if ok else '<span style="color:#f85149;">&#9679;</span>'
        st.markdown(f'<div style="font-size:11px; color:#8b949e; margin:3px 0;">{dot} {name} <span style="color:#6e7681;">:{port}</span></div>', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown('<div style="font-size:11px; color:#6e7681;"><b style="color:#8b949e;">Infrastructure</b><br><br>PostgreSQL (Docker)<br>Groq LLaMA 3.3 70B<br>FastAPI (port 18001)</div>', unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════
# PAGE: Command Center
# ════════════════════════════════════════════════════════════════════

if page == "Command Center":

    st.markdown("""
    <div class="hub-title">Command Center</div>
    <div class="hub-sub">Live KPIs across all revenue operations modules — refreshed every 30s</div>
    """, unsafe_allow_html=True)

    col_refresh, col_time = st.columns([1, 4])
    with col_refresh:
        if st.button("Refresh Now"):
            st.cache_data.clear()
            st.rerun()
    with col_time:
        st.markdown(f"<div style='color:#6e7681; font-size:12px; padding-top:8px;'>Last updated: {time.strftime('%H:%M:%S')}</div>", unsafe_allow_html=True)

    metrics = fetch_metrics()

    # ── Billing ──────────────────────────────────────────────────────
    st.markdown('<div class="section-header">💰 Billing</div>', unsafe_allow_html=True)
    bm = metrics.get("billing", {})
    b1, b2, b3, b4 = st.columns(4)

    with b1:
        overdue = bm.get("invoices_overdue", "—")
        color = "metric-danger" if isinstance(overdue, int) and overdue > 50 else "metric-warn"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Overdue Invoices</div>
            <div class="metric-value {color}">{overdue}</div>
            <div class="metric-sub">Require immediate follow-up</div>
        </div>""", unsafe_allow_html=True)

    with b2:
        leakage = bm.get("leakage_amount_flagged", 0)
        leakage_str = f"${leakage:,.2f}" if isinstance(leakage, (int, float)) else "—"
        color = "metric-danger" if isinstance(leakage, (int, float)) and leakage > 1000 else "metric-warn"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Revenue Leakage Flagged</div>
            <div class="metric-value {color}">{leakage_str}</div>
            <div class="metric-sub">Open anomalies total</div>
        </div>""", unsafe_allow_html=True)

    with b3:
        revenue = bm.get("revenue_collected_mtd", 0)
        revenue_str = f"${revenue:,.2f}" if isinstance(revenue, (int, float)) else "—"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Revenue Collected MTD</div>
            <div class="metric-value metric-good">{revenue_str}</div>
            <div class="metric-sub">Month-to-date payments</div>
        </div>""", unsafe_allow_html=True)

    with b4:
        anom_open = bm.get("anomalies_open", "—")
        anom_crit = bm.get("anomalies_critical", 0)
        color = "metric-danger" if isinstance(anom_crit, int) and anom_crit > 0 else "metric-warn"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Open Anomalies</div>
            <div class="metric-value {color}">{anom_open}</div>
            <div class="metric-sub">{anom_crit} critical</div>
        </div>""", unsafe_allow_html=True)

    # ── CPQ ──────────────────────────────────────────────────────────
    st.markdown('<div class="section-header">📋 CPQ — Configure, Price, Quote</div>', unsafe_allow_html=True)
    cm = metrics.get("cpq", {})
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        mrr = cm.get("total_mrr_pipeline", 0)
        mrr_str = f"${mrr:,.2f}" if isinstance(mrr, (int, float)) else "—"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">MRR Pipeline</div>
            <div class="metric-value metric-good">{mrr_str}</div>
            <div class="metric-sub">Draft + presented quotes</div>
        </div>""", unsafe_allow_html=True)

    with c2:
        avg_val = cm.get("avg_quote_value", 0)
        avg_str = f"${avg_val:,.2f}" if isinstance(avg_val, (int, float)) else "—"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Avg Quote Value</div>
            <div class="metric-value">{avg_str}</div>
            <div class="metric-sub">All-time average</div>
        </div>""", unsafe_allow_html=True)

    with c3:
        created = cm.get("quotes_created_today", "—")
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Quotes Created Today</div>
            <div class="metric-value">{created}</div>
            <div class="metric-sub">New proposals</div>
        </div>""", unsafe_allow_html=True)

    with c4:
        rate = cm.get("acceptance_rate_pct", 0)
        rate_str = f"{rate:.1f}%" if isinstance(rate, (int, float)) else "—"
        color = "metric-good" if isinstance(rate, (int, float)) and rate >= 50 else "metric-warn"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Acceptance Rate</div>
            <div class="metric-value {color}">{rate_str}</div>
            <div class="metric-sub">Quotes accepted today</div>
        </div>""", unsafe_allow_html=True)

    # ── ServiceDesk ───────────────────────────────────────────────────
    st.markdown('<div class="section-header">🎫 ServiceDesk — Customer Support</div>', unsafe_allow_html=True)
    sm = metrics.get("servicedesk", {})
    s1, s2, s3, s4 = st.columns(4)

    with s1:
        open_t = sm.get("tickets_open", "—")
        color = "metric-danger" if isinstance(open_t, int) and open_t > 150 else "metric-warn"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Open Tickets</div>
            <div class="metric-value {color}">{open_t}</div>
            <div class="metric-sub">Awaiting resolution</div>
        </div>""", unsafe_allow_html=True)

    with s2:
        crit_t = sm.get("tickets_critical_open", "—")
        color = "metric-danger" if isinstance(crit_t, int) and crit_t > 0 else "metric-good"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Critical Open</div>
            <div class="metric-value {color}">{crit_t}</div>
            <div class="metric-sub">Immediate escalation needed</div>
        </div>""", unsafe_allow_html=True)

    with s3:
        created_t = sm.get("tickets_created_today", "—")
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Created Today</div>
            <div class="metric-value">{created_t}</div>
            <div class="metric-sub">New support requests</div>
        </div>""", unsafe_allow_html=True)

    with s4:
        resolved_t = sm.get("tickets_resolved_today", "—")
        color = "metric-good" if isinstance(resolved_t, int) and resolved_t > 0 else ""
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Resolved Today</div>
            <div class="metric-value {color}">{resolved_t}</div>
            <div class="metric-sub">Closed tickets</div>
        </div>""", unsafe_allow_html=True)

    # ── FSM ───────────────────────────────────────────────────────────
    st.markdown('<div class="section-header">🔧 FSM — Field Service Management</div>', unsafe_allow_html=True)
    fm = metrics.get("fsm", {})
    f1, f2, f3, f4 = st.columns(4)

    with f1:
        util = fm.get("technician_utilisation_pct", 0)
        util_str = f"{util:.1f}%" if isinstance(util, (int, float)) else "—"
        color = "metric-good" if isinstance(util, (int, float)) and util >= 40 else "metric-warn"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Technician Utilisation</div>
            <div class="metric-value {color}">{util_str}</div>
            <div class="metric-sub">Currently on-job</div>
        </div>""", unsafe_allow_html=True)

    with f2:
        sched = fm.get("jobs_scheduled_today", "—")
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Jobs Today</div>
            <div class="metric-value">{sched}</div>
            <div class="metric-sub">Scheduled for today</div>
        </div>""", unsafe_allow_html=True)

    with f3:
        ip = fm.get("jobs_in_progress", "—")
        color = "metric-good" if isinstance(ip, int) and ip > 0 else ""
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">In Progress</div>
            <div class="metric-value {color}">{ip}</div>
            <div class="metric-sub">Active field jobs</div>
        </div>""", unsafe_allow_html=True)

    with f4:
        pending = fm.get("jobs_pending_assignment", "—")
        color = "metric-warn" if isinstance(pending, int) and pending > 0 else "metric-good"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Pending Assignment</div>
            <div class="metric-value {color}">{pending}</div>
            <div class="metric-sub">Awaiting technician</div>
        </div>""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════
# PAGE: AI Chat
# ════════════════════════════════════════════════════════════════════

elif page == "AI Chat":

    st.markdown("""
    <div class="hub-title">AI Operations Chat</div>
    <div class="hub-sub">Ask anything about your revenue operations — the Orchestrator routes to the right agent automatically</div>
    """, unsafe_allow_html=True)

    # Suggested queries
    st.markdown('<div class="section-header">Quick Queries</div>', unsafe_allow_html=True)

    suggested = {
        "Billing": "How many overdue invoices do we have and what is the total leakage?",
        "CPQ": "What internet products do we offer and at what prices?",
        "ServiceDesk": "Show me the critical open support tickets",
        "FSM": "Which technicians are available in the North zone?",
    }

    cols = st.columns(4)
    for i, (label, query) in enumerate(suggested.items()):
        with cols[i]:
            if st.button(f"{label}", key=f"quick_{label}"):
                st.session_state.pending_query = query

    st.markdown("---")

    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        if msg["role"] == "user":
            st.markdown(f'<div class="chat-user">You: {msg["content"]}</div>', unsafe_allow_html=True)
        else:
            agents_used = msg.get("agents_used", [msg.get("agent", "Agent")])
            mode = msg.get("mode", "single")
            routing_reason = msg.get("routing_reason", "")
            agent_responses = msg.get("agent_responses", {})

            badges = " ".join([f'<span class="agent-badge">{a}</span>' for a in agents_used])
            mode_color = {"parallel": "#d29922", "sequential": "#3fb950", "single": "#58a6ff"}.get(mode, "#8b949e")
            mode_badge = f'<span style="background:#21262d;border:1px solid #30363d;border-radius:20px;padding:2px 10px;font-size:11px;font-weight:600;color:{mode_color};margin-left:4px;">{mode.upper()}</span>'

            detail_html = ""
            if len(agent_responses) > 1:
                detail_html = "<details style='margin-top:10px;'><summary style='font-size:11px;color:#8b949e;cursor:pointer;'>Show individual agent responses</summary>"
                for domain, resp in agent_responses.items():
                    detail_html += f'<div style="margin-top:8px;padding:8px;background:#0d1117;border-radius:6px;font-size:12px;"><b style="color:#58a6ff;">[{domain}]</b><br>{str(resp)[:400]}...</div>'
                detail_html += "</details>"

            st.markdown(f"""
            <div class="chat-agent">
                <div style="margin-bottom:8px;">{badges}{mode_badge}</div>
                {msg["content"].replace(chr(10), "<br>")}
                {detail_html}
                <div class="routing-info">Reason: {routing_reason}</div>
            </div>""", unsafe_allow_html=True)

    # Input area
    st.markdown('<div class="section-header">Your Query</div>', unsafe_allow_html=True)
    col_input, col_btn = st.columns([5, 1])

    # Handle suggested query pre-fill
    default_val = st.session_state.pop("pending_query", "") if "pending_query" in st.session_state else ""

    with col_input:
        user_input = st.text_input(
            "Ask the AI agents...",
            value=default_val,
            placeholder="e.g. How many overdue invoices do we have?",
            label_visibility="collapsed",
            key="chat_input"
        )
    with col_btn:
        send = st.button("Send")

    if send and user_input.strip():
        query = user_input.strip()
        st.session_state.messages.append({"role": "user", "content": query})

        hint = "Running agents in parallel..." if any(w in query.lower() for w in [" and ", " also ", "both", "quote", "invoice", "install"]) else "Thinking..."
        with st.spinner(hint):
            try:
                result = ask_agent(query)
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": result["response"],
                    "agents_used": result["agents_used"],
                    "mode": result["mode"],
                    "routing_reason": result["routing_reason"],
                    "agent_responses": result["agent_responses"],
                })
            except Exception as e:
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": f"Error: {str(e)}",
                    "agents_used": ["System"],
                    "mode": "error",
                    "routing_reason": "",
                    "agent_responses": {},
                })
        st.rerun()

    if st.session_state.messages:
        if st.button("Clear Chat"):
            st.session_state.messages = []
            st.rerun()


# ════════════════════════════════════════════════════════════════════
# PAGE: About
# ════════════════════════════════════════════════════════════════════

elif page == "About":
    st.markdown("""
    <div class="hub-title">About HalfBill</div>
    <div class="hub-sub">Architecture and technical overview</div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="section-header">Architecture</div>', unsafe_allow_html=True)
    st.code("""
User Query (natural language)
        │
        ▼
  Orchestrator (keyword + LLM routing)
        │
   ┌────┴─────────────────┐
   │     Domain Agents    │
   ├──────────────────────┤
   │  Billing Agent       │ → /billing/* endpoints
   │  CPQ Agent           │ → /cpq/* endpoints
   │  ServiceDesk Agent   │ → /servicedesk/* endpoints
   │  FSM Agent           │ → /fsm/* endpoints
   └──────────────────────┘
        │
        ▼
  FastAPI REST API (port 18001)
        │
        ▼
  PostgreSQL + pgvector (Docker port 15432)
    """, language="text")

    st.markdown('<div class="section-header">Tech Stack</div>', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        **Backend**
        - FastAPI (Python 3.13)
        - asyncpg (async PostgreSQL)
        - pgvector (vector search ready)
        - Docker (database isolation)

        **AI Layer**
        - Groq API (LLaMA 3.3 70B)
        - Tool-use / function calling
        - Keyword + LLM routing
        """)
    with col2:
        st.markdown("""
        **Frontend**
        - Streamlit (this dashboard)
        - Custom dark theme CSS
        - Real-time KPI refresh

        **Modules**
        - CPQ (Configure, Price, Quote)
        - Billing (Invoices + Anomalies)
        - ServiceDesk (Support Tickets)
        - FSM (Field Service Jobs)
        """)
