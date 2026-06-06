from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
from datetime import date, datetime
import asyncpg

from infra.shared.db import get_db

router = APIRouter()

# ── Pydantic Models ───────────────────────────────────────────────────

class CreateInvoiceRequest(BaseModel):
    customer_id: int
    quote_id: Optional[int] = None
    billing_period_start: Optional[date] = None
    billing_period_end: Optional[date] = None
    notes: Optional[str] = None

class UpdateInvoiceStatusRequest(BaseModel):
    status: str  # draft, issued, paid, overdue, disputed, written_off

class CreatePaymentRequest(BaseModel):
    invoice_id: int
    amount: float
    payment_method: str  # credit_card, bank_transfer, check, cash, auto_pay
    transaction_ref: Optional[str] = None

class CreateAnomalyRequest(BaseModel):
    invoice_id: int
    anomaly_type: str
    severity: str
    amount_affected: Optional[float] = None
    description: str

class UpdateAnomalyStatusRequest(BaseModel):
    status: str  # open, investigating, resolved, dismissed
    resolution: Optional[str] = None


# ── Helper: fetch invoice dict ────────────────────────────────────────

async def fetch_invoice(conn, invoice_number: str):
    row = await conn.fetchrow("""
        SELECT i.id, i.invoice_number, i.customer_id, c.name AS customer_name,
               i.quote_id, i.status, i.billing_period_start, i.billing_period_end,
               i.due_date, i.subtotal, i.tax_rate, i.tax_amount,
               i.total_amount, i.paid_amount, i.balance_due, i.currency
        FROM billing_invoices i
        JOIN customers c ON c.id = i.customer_id
        WHERE i.invoice_number = $1
    """, invoice_number)
    if not row:
        raise HTTPException(status_code=404, detail=f"Invoice {invoice_number} not found")

    inv = dict(row)
    # Fetch line items
    line_rows = await conn.fetch("""
        SELECT li.id, li.product_id, p.name AS product_name, li.description,
               li.quantity, li.unit_price, li.subtotal, li.line_type
        FROM billing_invoice_line_items li
        LEFT JOIN products p ON p.id = li.product_id
        WHERE li.invoice_id = $1
    """, inv["id"])
    inv["line_items"] = [dict(lr) for lr in line_rows]
    # Convert dates to strings
    for field in ("billing_period_start", "billing_period_end", "due_date"):
        if inv.get(field):
            inv[field] = str(inv[field])
    return inv


# ── Invoices ──────────────────────────────────────────────────────────

@router.get("/invoices", summary="List invoices with optional status filter")
async def list_invoices(
    status: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
    conn: asyncpg.Connection = Depends(get_db)
):
    if status:
        rows = await conn.fetch("""
            SELECT i.id, i.invoice_number, i.customer_id, c.name AS customer_name,
                   i.quote_id, i.status, i.billing_period_start, i.billing_period_end,
                   i.due_date, i.subtotal, i.tax_rate, i.tax_amount,
                   i.total_amount, i.paid_amount, i.balance_due, i.currency
            FROM billing_invoices i JOIN customers c ON c.id = i.customer_id
            WHERE i.status = $1
            ORDER BY i.created_at DESC LIMIT $2
        """, status, limit)
    else:
        rows = await conn.fetch("""
            SELECT i.id, i.invoice_number, i.customer_id, c.name AS customer_name,
                   i.quote_id, i.status, i.billing_period_start, i.billing_period_end,
                   i.due_date, i.subtotal, i.tax_rate, i.tax_amount,
                   i.total_amount, i.paid_amount, i.balance_due, i.currency
            FROM billing_invoices i JOIN customers c ON c.id = i.customer_id
            ORDER BY i.created_at DESC LIMIT $1
        """, limit)

    result = []
    for r in rows:
        d = dict(r)
        for field in ("billing_period_start", "billing_period_end", "due_date"):
            if d.get(field):
                d[field] = str(d[field])
        d["line_items"] = []
        result.append(d)
    return result


@router.get("/invoices/overdue", summary="Get all overdue invoices")
async def get_overdue_invoices(conn: asyncpg.Connection = Depends(get_db)):
    rows = await conn.fetch("""
        SELECT i.id, i.invoice_number, i.customer_id, c.name AS customer_name,
               i.quote_id, i.status, i.billing_period_start, i.billing_period_end,
               i.due_date, i.subtotal, i.tax_rate, i.tax_amount,
               i.total_amount, i.paid_amount, i.balance_due, i.currency
        FROM billing_invoices i JOIN customers c ON c.id = i.customer_id
        WHERE i.status = 'overdue'
        ORDER BY i.due_date ASC
    """)
    result = []
    for r in rows:
        d = dict(r)
        for field in ("billing_period_start", "billing_period_end", "due_date"):
            if d.get(field):
                d[field] = str(d[field])
        d["line_items"] = []
        result.append(d)
    return result


@router.get("/invoices/customer/{customer_id}", summary="Get all invoices for a customer")
async def get_customer_invoices(customer_id: int, conn: asyncpg.Connection = Depends(get_db)):
    rows = await conn.fetch("""
        SELECT i.id, i.invoice_number, i.customer_id, c.name AS customer_name,
               i.quote_id, i.status, i.billing_period_start, i.billing_period_end,
               i.due_date, i.subtotal, i.tax_rate, i.tax_amount,
               i.total_amount, i.paid_amount, i.balance_due, i.currency
        FROM billing_invoices i JOIN customers c ON c.id = i.customer_id
        WHERE i.customer_id = $1
        ORDER BY i.created_at DESC
    """, customer_id)
    result = []
    for r in rows:
        d = dict(r)
        for field in ("billing_period_start", "billing_period_end", "due_date"):
            if d.get(field):
                d[field] = str(d[field])
        d["line_items"] = []
        result.append(d)
    return result


@router.get("/invoices/{invoice_number}", summary="Get one invoice by number")
async def get_invoice(invoice_number: str, conn: asyncpg.Connection = Depends(get_db)):
    return await fetch_invoice(conn, invoice_number)


@router.post("/invoices", status_code=201, summary="Create a new invoice")
async def create_invoice(body: CreateInvoiceRequest, conn: asyncpg.Connection = Depends(get_db)):
    # Validate customer
    customer = await conn.fetchrow("SELECT id FROM customers WHERE id = $1", body.customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail=f"Customer {body.customer_id} not found")

    # Generate invoice number
    count = await conn.fetchval("SELECT COUNT(*) FROM billing_invoices")
    year = datetime.now().year
    inv_number = f"INV-{year}-{(count + 1):05d}"

    # Calculate totals
    subtotal = 0.0
    if body.quote_id:
        quote_total = await conn.fetchval(
            "SELECT total_value FROM cpq_quotes WHERE id = $1", body.quote_id
        )
        if not quote_total:
            raise HTTPException(status_code=404, detail=f"Quote {body.quote_id} not found")
        subtotal = float(quote_total)

    TAX_RATE = 8.5
    tax_amount = round(subtotal * TAX_RATE / 100, 2)
    total_amount = round(subtotal + tax_amount, 2)

    # Due date = billing_period_end + 14 days or 14 days from now
    from datetime import timedelta
    due_date = None
    if body.billing_period_end:
        due_date = body.billing_period_end + timedelta(days=14)

    inv_id = await conn.fetchval("""
        INSERT INTO billing_invoices
            (invoice_number, customer_id, quote_id, status,
             billing_period_start, billing_period_end, due_date,
             subtotal, tax_rate, tax_amount, total_amount, notes)
        VALUES ($1,$2,$3,'draft',$4,$5,$6,$7,$8,$9,$10,$11)
        RETURNING id
    """, inv_number, body.customer_id, body.quote_id,
         body.billing_period_start, body.billing_period_end, due_date,
         subtotal, TAX_RATE, tax_amount, total_amount, body.notes)

    return await fetch_invoice(conn, inv_number)


@router.put("/invoices/{invoice_number}/status", summary="Update invoice status")
async def update_invoice_status(
    invoice_number: str,
    body: UpdateInvoiceStatusRequest,
    conn: asyncpg.Connection = Depends(get_db)
):
    updated = await conn.execute("""
        UPDATE billing_invoices SET status = $1, updated_at = NOW()
        WHERE invoice_number = $2
    """, body.status, invoice_number)
    if updated == "UPDATE 0":
        raise HTTPException(status_code=404, detail=f"Invoice {invoice_number} not found")
    return await fetch_invoice(conn, invoice_number)


# ── Payments ──────────────────────────────────────────────────────────

@router.get("/payments/invoice/{invoice_number}", summary="Get payments for an invoice")
async def get_invoice_payments(invoice_number: str, conn: asyncpg.Connection = Depends(get_db)):
    inv = await conn.fetchrow(
        "SELECT id FROM billing_invoices WHERE invoice_number = $1", invoice_number
    )
    if not inv:
        raise HTTPException(status_code=404, detail=f"Invoice {invoice_number} not found")
    rows = await conn.fetch("""
        SELECT id, invoice_id, customer_id, amount, payment_method, status,
               transaction_ref, paid_at
        FROM billing_payments WHERE invoice_id = $1
        ORDER BY paid_at DESC
    """, inv["id"])
    result = []
    for r in rows:
        d = dict(r)
        if d.get("paid_at"):
            d["paid_at"] = str(d["paid_at"])
        result.append(d)
    return result


@router.post("/payments", status_code=201, summary="Record a payment")
async def record_payment(body: CreatePaymentRequest, conn: asyncpg.Connection = Depends(get_db)):
    inv = await conn.fetchrow("""
        SELECT id, invoice_number, total_amount, paid_amount
        FROM billing_invoices WHERE id = $1
    """, body.invoice_id)
    if not inv:
        raise HTTPException(status_code=404, detail=f"Invoice ID {body.invoice_id} not found")

    now = datetime.utcnow()
    pay_id = await conn.fetchval("""
        INSERT INTO billing_payments
            (invoice_id, customer_id, amount, payment_method, status, transaction_ref, paid_at)
        SELECT $1, customer_id, $2, $3, 'completed', $4, $5 FROM billing_invoices WHERE id = $1
        RETURNING id
    """, body.invoice_id, body.amount, body.payment_method, body.transaction_ref, now)

    # Update invoice paid_amount, auto-mark paid if fully settled
    new_paid = float(inv["paid_amount"]) + body.amount
    new_status = "paid" if new_paid >= float(inv["total_amount"]) else None
    if new_status:
        await conn.execute("""
            UPDATE billing_invoices SET paid_amount = $1, status = $2, updated_at = NOW()
            WHERE id = $3
        """, new_paid, new_status, body.invoice_id)
    else:
        await conn.execute("""
            UPDATE billing_invoices SET paid_amount = $1, updated_at = NOW()
            WHERE id = $2
        """, new_paid, body.invoice_id)

    row = await conn.fetchrow("""
        SELECT id, invoice_id, customer_id, amount, payment_method, status,
               transaction_ref, paid_at
        FROM billing_payments WHERE id = $1
    """, pay_id)
    d = dict(row)
    if d.get("paid_at"):
        d["paid_at"] = str(d["paid_at"])
    return d


# ── Anomalies ─────────────────────────────────────────────────────────

async def fetch_anomaly(conn, anomaly_id: int):
    row = await conn.fetchrow("""
        SELECT a.id, a.invoice_id, i.invoice_number, a.customer_id, c.name AS customer_name,
               a.anomaly_type, a.severity, a.amount_affected, a.description,
               a.status, a.detected_at, a.resolved_at
        FROM billing_anomalies a
        JOIN billing_invoices i ON i.id = a.invoice_id
        JOIN customers c ON c.id = a.customer_id
        WHERE a.id = $1
    """, anomaly_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Anomaly {anomaly_id} not found")
    d = dict(row)
    for field in ("detected_at", "resolved_at"):
        if d.get(field):
            d[field] = str(d[field])
    return d


@router.get("/anomalies", summary="List anomalies with optional filters")
async def list_anomalies(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    conn: asyncpg.Connection = Depends(get_db)
):
    conditions = []
    params = []
    if status:
        params.append(status)
        conditions.append(f"a.status = ${len(params)}")
    if severity:
        params.append(severity)
        conditions.append(f"a.severity = ${len(params)}")

    where = "WHERE " + " AND ".join(conditions) if conditions else ""

    rows = await conn.fetch(f"""
        SELECT a.id, a.invoice_id, i.invoice_number, a.customer_id, c.name AS customer_name,
               a.anomaly_type, a.severity, a.amount_affected, a.description,
               a.status, a.detected_at, a.resolved_at
        FROM billing_anomalies a
        JOIN billing_invoices i ON i.id = a.invoice_id
        JOIN customers c ON c.id = a.customer_id
        {where}
        ORDER BY a.detected_at DESC
    """, *params)

    result = []
    for r in rows:
        d = dict(r)
        for field in ("detected_at", "resolved_at"):
            if d.get(field):
                d[field] = str(d[field])
        result.append(d)
    return result


@router.get("/anomalies/open", summary="Get all open anomalies by severity")
async def get_open_anomalies(conn: asyncpg.Connection = Depends(get_db)):
    rows = await conn.fetch("""
        SELECT a.id, a.invoice_id, i.invoice_number, a.customer_id, c.name AS customer_name,
               a.anomaly_type, a.severity, a.amount_affected, a.description,
               a.status, a.detected_at, a.resolved_at
        FROM billing_anomalies a
        JOIN billing_invoices i ON i.id = a.invoice_id
        JOIN customers c ON c.id = a.customer_id
        WHERE a.status = 'open'
        ORDER BY CASE a.severity
            WHEN 'critical' THEN 1 WHEN 'high' THEN 2
            WHEN 'medium' THEN 3 ELSE 4 END
    """)
    result = []
    for r in rows:
        d = dict(r)
        for field in ("detected_at", "resolved_at"):
            if d.get(field):
                d[field] = str(d[field])
        result.append(d)
    return result


@router.get("/anomalies/{anomaly_id}", summary="Get one anomaly by ID")
async def get_anomaly(anomaly_id: int, conn: asyncpg.Connection = Depends(get_db)):
    return await fetch_anomaly(conn, anomaly_id)


@router.post("/anomalies", status_code=201, summary="Flag a billing anomaly")
async def create_anomaly(body: CreateAnomalyRequest, conn: asyncpg.Connection = Depends(get_db)):
    inv = await conn.fetchrow(
        "SELECT id, customer_id FROM billing_invoices WHERE id = $1", body.invoice_id
    )
    if not inv:
        raise HTTPException(status_code=404, detail=f"Invoice ID {body.invoice_id} not found")

    anomaly_id = await conn.fetchval("""
        INSERT INTO billing_anomalies
            (invoice_id, customer_id, anomaly_type, severity, amount_affected, description, status)
        VALUES ($1, $2, $3, $4, $5, $6, 'open')
        RETURNING id
    """, body.invoice_id, inv["customer_id"], body.anomaly_type,
         body.severity, body.amount_affected, body.description)

    return await fetch_anomaly(conn, anomaly_id)


@router.put("/anomalies/{anomaly_id}/status", summary="Resolve or dismiss an anomaly")
async def update_anomaly_status(
    anomaly_id: int,
    body: UpdateAnomalyStatusRequest,
    conn: asyncpg.Connection = Depends(get_db)
):
    resolved_at = datetime.utcnow() if body.status in ("resolved", "dismissed") else None
    updated = await conn.execute("""
        UPDATE billing_anomalies
        SET status = $1, resolved_at = $2
        WHERE id = $3
    """, body.status, resolved_at, anomaly_id)
    if updated == "UPDATE 0":
        raise HTTPException(status_code=404, detail=f"Anomaly {anomaly_id} not found")
    return await fetch_anomaly(conn, anomaly_id)


# ── Metrics ───────────────────────────────────────────────────────────

@router.get("/metrics", summary="Billing metrics for Agentic Hub")
async def get_billing_metrics(conn: asyncpg.Connection = Depends(get_db)):
    today = date.today()
    issued_today = await conn.fetchval(
        "SELECT COUNT(*) FROM billing_invoices WHERE DATE(issued_at) = $1", today
    ) or 0
    paid_today = await conn.fetchval(
        "SELECT COUNT(*) FROM billing_invoices WHERE status='paid' AND DATE(updated_at)=$1", today
    ) or 0
    overdue_count = await conn.fetchval(
        "SELECT COUNT(*) FROM billing_invoices WHERE status='overdue'"
    ) or 0
    revenue_mtd = await conn.fetchval("""
        SELECT COALESCE(SUM(amount),0) FROM billing_payments
        WHERE status='completed' AND DATE_TRUNC('month', paid_at) = DATE_TRUNC('month', NOW())
    """) or 0
    anomalies_open = await conn.fetchval(
        "SELECT COUNT(*) FROM billing_anomalies WHERE status='open'"
    ) or 0
    anomalies_critical = await conn.fetchval(
        "SELECT COUNT(*) FROM billing_anomalies WHERE status='open' AND severity='critical'"
    ) or 0
    leakage = await conn.fetchval(
        "SELECT COALESCE(SUM(amount_affected),0) FROM billing_anomalies WHERE status='open'"
    ) or 0

    return {
        "invoices_issued_today": int(issued_today),
        "invoices_paid_today": int(paid_today),
        "invoices_overdue": int(overdue_count),
        "revenue_collected_mtd": float(revenue_mtd),
        "anomalies_open": int(anomalies_open),
        "anomalies_critical": int(anomalies_critical),
        "leakage_amount_flagged": float(leakage),
    }
