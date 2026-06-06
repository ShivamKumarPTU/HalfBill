import sys
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Add project root to path so we can import config
# Add project root so 'infra', 'fastapi_app', 'config' are importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))
from config import PRODUCT_API_PORT

# Import our router stubs
from fastapi_app.routers import cpq, billing, servicedesk, fsm

app = FastAPI(
    title="Project HalfBill — Product API",
    description="REST API layer for all four OneBill product modules.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Product routers ───────────────────────────────────────────
app.include_router(cpq.router, prefix="/cpq", tags=["CPQ"])
app.include_router(billing.router, prefix="/billing", tags=["Billing"])
app.include_router(servicedesk.router, prefix="/servicedesk", tags=["ServiceDesk"])
app.include_router(fsm.router, prefix="/fsm", tags=["FSM"])

@app.get("/health")
async def health():
    return {"status": "ok", "service": "product-fastapi", "port": PRODUCT_API_PORT}

@app.get("/")
async def root():
    return {"message": "Project HalfBill Product API", "docs": "/docs"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("fastapi_app.main:app", host="0.0.0.0", port=PRODUCT_API_PORT, reload=True)
