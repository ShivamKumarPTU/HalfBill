from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, field_validator
from typing import List, Optional
from datetime import date, datetime, timedelta
import asyncpg

from infra.shared.db import get_db

router = APIRouter()

# ── Pydantic Models ───────────────────────────────────────────────────

class QuoteLineItemIn(BaseModel):
    product_id: int
    quantity: int = 1
    discount_percent: float = 0.0

    @field_validator("discount_percent")
    @classmethod
    def cap_line_discount(cls, v):
        if v < 0 or v > 30:
            raise ValueError("Line item discount must be between 0 and 30%")
        return v

class CreateQuoteRequest(BaseModel):
    customer_id: int
    line_items: List[QuoteLineItemIn]
    discount_percent: float = 0.0
    discount_reason: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("discount_percent")
    @classmethod
    def cap_discount(cls, v):
        if v < 0 or v > 30:
            raise ValueError("Quote discount cannot exceed 30%")
        return v

class UpdateQuoteStatusRequest(BaseModel):
    status: str   # draft, presented, accepted, rejected, expired
    notes: Optional[str] = None

class ApplyDiscountRequest(BaseModel):
    discount_percent: float
    reason: str

    @field_validator("discount_percent")
    @classmethod
    def cap_discount(cls, v):
        if v < 0 or v > 30:
            raise ValueError("Discount cannot exceed 30% (business rule)")
        return v


# ── Helper: full quote fetch ──────────────────────────────────────────

async def fetch_quote(conn, quote_number: str):
    row = await conn.fetchrow("""
        SELECT q.id, q.quote_number, q.customer_id, c.name AS customer_name,
               q.status, q.total_mrr, q.total_otc, q.total_value,
               q.discount_percent, q.discount_reason, q.valid_until,
               q.notes, q.created_by
        FROM cpq_quotes q JOIN customers c ON c.id = q.customer_id
        WHERE q.quote_number = $1
    """, quote_number)
    if not row:
        raise HTTPException(status_code=404, detail=f"Quote {quote_number} not found")
    q = dict(row)
    if q.get("valid_until"):
        q["valid_until"] = str(q["valid_until"])

    line_rows = await conn.fetch("""
        SELECT li.id, li.product_id, p.name AS product_name, li.quantity,
               li.list_price, li.discount_percent, li.unit_price, li.subtotal, li.is_recurring
        FROM cpq_quote_line_items li JOIN products p ON p.id = li.product_id
        WHERE li.quote_id = $1
    """, q["id"])
    q["line_items"] = [dict(lr) for lr in line_rows]
    return q


# ── Products ──────────────────────────────────────────────────────────

@router.get("/products", summary="List all active products")
async def list_products(conn: asyncpg.Connection = Depends(get_db)):
    rows = await conn.fetch("""
        SELECT id, product_code, name, category, billing_type, contract_type,
               base_price, setup_fee, description
        FROM products WHERE is_active = TRUE ORDER BY category, name
    """)
    return [dict(r) for r in rows]


@router.get("/products/search", summary="Search products by name or description")
async def search_products(
    q: str = Query(..., min_length=2),
    conn: asyncpg.Connection = Depends(get_db)
):
    rows = await conn.fetch("""
        SELECT id, product_code, name, category, billing_type, contract_type,
               base_price, setup_fee, description
        FROM products WHERE is_active = TRUE AND (name ILIKE $1 OR description ILIKE $1)
    """, f"%{q}%")
    return [dict(r) for r in rows]


@router.get("/products/{product_id}", summary="Get one product by ID")
async def get_product(product_id: int, conn: asyncpg.Connection = Depends(get_db)):
    row = await conn.fetchrow("""
        SELECT id, product_code, name, category, billing_type, contract_type,
               base_price, setup_fee, description
        FROM products WHERE id = $1 AND is_active = TRUE
    """, product_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")
    return dict(row)


# ── Customers ─────────────────────────────────────────────────────────

@router.get("/customers", summary="List customers (paginated)")
async def list_customers(
    limit: int = Query(20, ge=1, le=100),
    conn: asyncpg.Connection = Depends(get_db)
):
    rows = await conn.fetch("""
        SELECT id, customer_code, name, email, account_type, status, city, state
        FROM customers ORDER BY id LIMIT $1
    """, limit)
    return [dict(r) for r in rows]


@router.get("/customers/search", summary="Find customers by name")
async def search_customers(
    name: str = Query(..., min_length=2),
    conn: asyncpg.Connection = Depends(get_db)
):
    rows = await conn.fetch("""
        SELECT id, customer_code, name, email, account_type, status, city, state
        FROM customers WHERE name ILIKE $1 ORDER BY name
    """, f"%{name}%")
    return [dict(r) for r in rows]


@router.get("/customers/{customer_id}", summary="Get one customer by ID")
async def get_customer(customer_id: int, conn: asyncpg.Connection = Depends(get_db)):
    row = await conn.fetchrow("""
        SELECT id, customer_code, name, email, account_type, status, city, state
        FROM customers WHERE id = $1
    """, customer_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Customer {customer_id} not found")
    return dict(row)


# ── Quotes ────────────────────────────────────────────────────────────

@router.get("/quotes", summary="List quotes with optional status filter")
async def list_quotes(
    status: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
    conn: asyncpg.Connection = Depends(get_db)
):
    if status:
        rows = await conn.fetch("""
            SELECT q.id, q.quote_number, q.customer_id, c.name AS customer_name,
                   q.status, q.total_mrr, q.total_otc, q.total_value,
                   q.discount_percent, q.discount_reason, q.valid_until, q.notes, q.created_by
            FROM cpq_quotes q JOIN customers c ON c.id = q.customer_id
            WHERE q.status = $1 ORDER BY q.created_at DESC LIMIT $2
        """, status, limit)
    else:
        rows = await conn.fetch("""
            SELECT q.id, q.quote_number, q.customer_id, c.name AS customer_name,
                   q.status, q.total_mrr, q.total_otc, q.total_value,
                   q.discount_percent, q.discount_reason, q.valid_until, q.notes, q.created_by
            FROM cpq_quotes q JOIN customers c ON c.id = q.customer_id
            ORDER BY q.created_at DESC LIMIT $1
        """, limit)
    result = []
    for r in rows:
        d = dict(r)
        if d.get("valid_until"):
            d["valid_until"] = str(d["valid_until"])
        d["line_items"] = []
        result.append(d)
    return result


@router.get("/quotes/customer/{customer_id}", summary="Get all quotes for a customer")
async def get_customer_quotes(customer_id: int, conn: asyncpg.Connection = Depends(get_db)):
    rows = await conn.fetch("""
        SELECT q.id, q.quote_number, q.customer_id, c.name AS customer_name,
               q.status, q.total_mrr, q.total_otc, q.total_value,
               q.discount_percent, q.discount_reason, q.valid_until, q.notes, q.created_by
        FROM cpq_quotes q JOIN customers c ON c.id = q.customer_id
        WHERE q.customer_id = $1 ORDER BY q.created_at DESC
    """, customer_id)
    result = []
    for r in rows:
        d = dict(r)
        if d.get("valid_until"):
            d["valid_until"] = str(d["valid_until"])
        d["line_items"] = []
        result.append(d)
    return result


@router.get("/quotes/{quote_number}", summary="Get one quote by number")
async def get_quote(quote_number: str, conn: asyncpg.Connection = Depends(get_db)):
    return await fetch_quote(conn, quote_number)


@router.post("/quotes", status_code=201, summary="Create a new multi-item quote")
async def create_quote(body: CreateQuoteRequest, conn: asyncpg.Connection = Depends(get_db)):
    # Validate customer exists
    cust = await conn.fetchrow("SELECT id FROM customers WHERE id = $1", body.customer_id)
    if not cust:
        raise HTTPException(status_code=404, detail=f"Customer {body.customer_id} not found")

    # Generate quote number
    count = await conn.fetchval("SELECT COUNT(*) FROM cpq_quotes")
    year = datetime.now().year
    quote_number = f"QT-{year}-{(count + 1):05d}"

    # Calculate totals from line items
    total_mrr = 0.0
    total_otc = 0.0
    line_data = []

    for item in body.line_items:
        prod = await conn.fetchrow(
            "SELECT id, base_price, billing_type FROM products WHERE id = $1 AND is_active = TRUE",
            item.product_id
        )
        if not prod:
            raise HTTPException(status_code=404, detail=f"Product {item.product_id} not found")

        list_price = float(prod["base_price"])
        unit_price = round(list_price * (1 - item.discount_percent / 100), 2)
        subtotal = round(unit_price * item.quantity, 2)
        is_recurring = prod["billing_type"] in ("monthly", "annual", "prepaid")

        if is_recurring:
            total_mrr += subtotal
        else:
            total_otc += subtotal

        line_data.append({
            "product_id": item.product_id,
            "quantity": item.quantity,
            "list_price": list_price,
            "discount_percent": item.discount_percent,
            "unit_price": unit_price,
            "subtotal": subtotal,
            "is_recurring": is_recurring,
        })

    # Apply quote-level discount
    total_value = round((total_mrr + total_otc) * (1 - body.discount_percent / 100), 2)
    valid_until = date.today() + timedelta(days=30)

    quote_id = await conn.fetchval("""
        INSERT INTO cpq_quotes
            (quote_number, customer_id, status, total_mrr, total_otc, total_value,
             discount_percent, discount_reason, valid_until, notes, created_by)
        VALUES ($1,$2,'draft',$3,$4,$5,$6,$7,$8,$9,'system')
        RETURNING id
    """, quote_number, body.customer_id, total_mrr, total_otc, total_value,
         body.discount_percent, body.discount_reason, valid_until, body.notes)

    # Insert line items
    for ld in line_data:
        await conn.execute("""
            INSERT INTO cpq_quote_line_items
                (quote_id, product_id, quantity, list_price, discount_percent,
                 unit_price, subtotal, is_recurring)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
        """, quote_id, ld["product_id"], ld["quantity"], ld["list_price"],
             ld["discount_percent"], ld["unit_price"], ld["subtotal"], ld["is_recurring"])

    # Record in status history
    await conn.execute("""
        INSERT INTO cpq_quote_status_history (quote_id, new_status, changed_by)
        VALUES ($1, 'draft', 'system')
    """, quote_id)

    return await fetch_quote(conn, quote_number)


@router.put("/quotes/{quote_number}/status", summary="Update quote status")
async def update_quote_status(
    quote_number: str,
    body: UpdateQuoteStatusRequest,
    conn: asyncpg.Connection = Depends(get_db)
):
    row = await conn.fetchrow(
        "SELECT id, status FROM cpq_quotes WHERE quote_number = $1", quote_number
    )
    if not row:
        raise HTTPException(status_code=404, detail=f"Quote {quote_number} not found")

    old_status = row["status"]
    await conn.execute("""
        UPDATE cpq_quotes SET status = $1, updated_at = NOW() WHERE quote_number = $2
    """, body.status, quote_number)

    await conn.execute("""
        INSERT INTO cpq_quote_status_history (quote_id, old_status, new_status, changed_by, notes)
        VALUES ($1, $2, $3, 'system', $4)
    """, row["id"], old_status, body.status, body.notes)

    return await fetch_quote(conn, quote_number)


@router.post("/quotes/{quote_number}/discount", summary="Apply or update discount (max 30%)")
async def apply_discount(
    quote_number: str,
    body: ApplyDiscountRequest,
    conn: asyncpg.Connection = Depends(get_db)
):
    row = await conn.fetchrow(
        "SELECT id, status, total_mrr, total_otc FROM cpq_quotes WHERE quote_number = $1",
        quote_number
    )
    if not row:
        raise HTTPException(status_code=404, detail=f"Quote {quote_number} not found")
    if row["status"] not in ("draft", "presented"):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot discount a quote with status '{row['status']}'"
        )

    new_total = round((float(row["total_mrr"]) + float(row["total_otc"])) *
                      (1 - body.discount_percent / 100), 2)

    await conn.execute("""
        UPDATE cpq_quotes
        SET discount_percent = $1, discount_reason = $2, total_value = $3, updated_at = NOW()
        WHERE quote_number = $4
    """, body.discount_percent, body.reason, new_total, quote_number)

    return await fetch_quote(conn, quote_number)


# ── Metrics ───────────────────────────────────────────────────────────

@router.get("/metrics", summary="CPQ business metrics")
async def get_cpq_metrics(conn: asyncpg.Connection = Depends(get_db)):
    today = date.today()
    created_today = await conn.fetchval(
        "SELECT COUNT(*) FROM cpq_quotes WHERE DATE(created_at) = $1", today
    ) or 0
    accepted_today = await conn.fetchval(
        "SELECT COUNT(*) FROM cpq_quotes WHERE status='accepted' AND DATE(updated_at)=$1", today
    ) or 0
    acceptance_rate = round((int(accepted_today) / max(int(created_today), 1)) * 100, 1)
    mrr_pipeline = await conn.fetchval(
        "SELECT COALESCE(SUM(total_mrr),0) FROM cpq_quotes WHERE status IN ('draft','presented')"
    ) or 0
    avg_value = await conn.fetchval(
        "SELECT COALESCE(AVG(total_value),0) FROM cpq_quotes"
    ) or 0

    return {
        "quotes_created_today": int(created_today),
        "quotes_accepted_today": int(accepted_today),
        "acceptance_rate_pct": acceptance_rate,
        "total_mrr_pipeline": float(mrr_pipeline),
        "avg_quote_value": round(float(avg_value), 2),
    }
