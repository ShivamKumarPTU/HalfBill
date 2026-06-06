import sys
sys.path.insert(0, '.')
from orchestrator.router import route

tests = [
    "Show me all overdue invoices",
    "A customer has both an overdue invoice and an open support ticket",
    "Create a quote for fiber internet then generate the invoice and schedule install",
    "What technicians are available in the North zone?",
    "We need to quote a customer for fiber internet and also schedule their installation",
]

for q in tests:
    r = route(q)
    print(f"Q: {q[:65]}")
    print(f"   Agents: {r['agents']}  Mode: {r['mode']}")
    print(f"   Reason: {r.get('reason','')}")
    print()
