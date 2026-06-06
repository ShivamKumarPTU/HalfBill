from pydantic import BaseModel
from typing import Optional

# ── Shared reference models ───────────────────────────────────
class CustomerSummary(BaseModel):
    id: int
    customer_code: str
    name: str
    email: str
    account_type: str
    status: str
    city: Optional[str]
    state: Optional[str]

class ProductSummary(BaseModel):
    id: int
    product_code: str
    name: str
    category: str
    billing_type: str
    contract_type: str
    base_price: float
    setup_fee: float
    description: Optional[str]

# ── Health response ───────────────────────────────────────────
class HealthResponse(BaseModel):
    status: str
    server: str
    port: int

# ── Error response ────────────────────────────────────────────
class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
