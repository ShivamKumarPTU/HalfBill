import sys
sys.path.insert(0, '.')
from agents.billing.billing_agent import chat

result = chat("What are our billing metrics right now?")
print(result)
