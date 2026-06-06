import sys
sys.path.insert(0, '.')
from orchestrator import route_and_respond

questions = [
    "How many overdue invoices do we have and what is the total leakage amount?",
    "Show me available fiber technicians in the North zone",
    "What are our most critical open support tickets right now?",
    "What internet products do we offer and what are their prices?",
]

for q in questions:
    print("\n" + "="*65)
    print(f"Q: {q}")
    print("="*65)
    result = route_and_respond(q, verbose=True)
    print(f"\n{result['agent']}:")
    print(result['response'])
    print()
