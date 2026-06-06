"""
start_all.py — Launch all HalfBill services in separate processes.
Run once: py start_all.py
Stop all: Ctrl+C (sends SIGTERM to all children)
"""

import subprocess
import sys
import os
import time
import signal

PYTHON = sys.executable
CWD = os.path.dirname(os.path.abspath(__file__))

SERVICES = [
    # (label, command, port)
    ("FastAPI  (REST API)",   [PYTHON, "-m", "uvicorn", "fastapi_app.main:app", "--host", "0.0.0.0", "--port", "18001"], 18001),
    ("CPQ MCP",               [PYTHON, "mcp_servers/cpq_mcp.py"],           18003),
    ("Billing MCP",           [PYTHON, "mcp_servers/billing_mcp.py"],        18004),
    ("ServiceDesk MCP",       [PYTHON, "mcp_servers/sd_mcp.py"],             18005),
    ("FSM MCP",               [PYTHON, "mcp_servers/fsm_mcp.py"],            18006),
    ("Orchestrator MCP",      [PYTHON, "orchestrator/orchestrator_server.py"], 18002),
    ("Streamlit Hub",         [PYTHON, "-m", "streamlit", "run", "hub.py",
                               "--server.port", "18501",
                               "--browser.gatherUsageStats", "false"],        18501),
]

processes = []


def start_all():
    print("\n" + "=" * 60)
    print("  HalfBill — Starting All Services")
    print("=" * 60)

    for label, cmd, port in SERVICES:
        print(f"  Starting {label:25s} -> port {port} ...", end=" ")
        p = subprocess.Popen(
            cmd,
            cwd=CWD,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        processes.append((label, p))
        time.sleep(1.5)  # stagger startup to avoid port conflicts
        print("OK" if p.poll() is None else "FAILED")

    print("\n" + "=" * 60)
    print("  All services started. Access points:")
    print("  FastAPI Docs      -> http://localhost:18001/docs")
    print("  Orchestrator MCP  -> http://localhost:18002/query")
    print("  CPQ MCP           -> http://localhost:18003/sse")
    print("  Billing MCP       -> http://localhost:18004/sse")
    print("  ServiceDesk MCP   -> http://localhost:18005/sse")
    print("  FSM MCP           -> http://localhost:18006/sse")
    print("  Streamlit Hub     -> http://localhost:18501")
    print("=" * 60)
    print("  Press Ctrl+C to stop all services\n")


def stop_all(sig=None, frame=None):
    print("\n  Stopping all services...")
    for label, p in processes:
        p.terminate()
        print(f"  Stopped {label}")
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, stop_all)
    signal.signal(signal.SIGTERM, stop_all)
    start_all()

    # Keep alive
    while True:
        time.sleep(5)
        for label, p in processes:
            if p.poll() is not None:
                print(f"  [WARN] {label} exited with code {p.returncode}")
