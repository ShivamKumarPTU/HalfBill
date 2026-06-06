from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, date
import asyncpg

from infra.shared.db import get_db

router = APIRouter()

# ── Pydantic Models ───────────────────────────────────────────────────

class CreateTicketRequest(BaseModel):
    customer_id: int
    category_id: Optional[int] = None
    invoice_id: Optional[int] = None
    anomaly_id: Optional[int] = None
    subject: str
    description: Optional[str] = None
    priority: str = "medium"
    channel: Optional[str] = "portal"

class UpdateTicketStatusRequest(BaseModel):
    status: str
    resolution: Optional[str] = None
    notes: Optional[str] = None

class AddCommentRequest(BaseModel):
    author: str
    comment: str
    is_internal: bool = False


# ── Helpers ───────────────────────────────────────────────────────────

def serialize_dates(d: dict) -> dict:
    for field in ("created_at", "updated_at", "resolved_at"):
        if d.get(field):
            d[field] = str(d[field])
    return d

async def fetch_ticket(conn, ticket_number: str):
    row = await conn.fetchrow("""
        SELECT t.id, t.ticket_number, t.customer_id, c.name AS customer_name,
               t.invoice_id, t.anomaly_id, t.category_id, cat.name AS category_name,
               t.subject, t.description, t.status, t.priority, t.channel,
               t.assigned_to, t.resolution, t.created_at, t.updated_at, t.resolved_at
        FROM servicedesk_tickets t
        JOIN customers c ON c.id = t.customer_id
        LEFT JOIN servicedesk_categories cat ON cat.id = t.category_id
        WHERE t.ticket_number = $1
    """, ticket_number)
    if not row:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_number} not found")
    t = serialize_dates(dict(row))
    comments = await conn.fetch("""
        SELECT id, author, comment, is_internal, created_at
        FROM servicedesk_ticket_comments WHERE ticket_id = $1 ORDER BY created_at
    """, t["id"])
    t["comments"] = [{**dict(c), "created_at": str(c["created_at"])} for c in comments]
    return t


# ── Endpoints ─────────────────────────────────────────────────────────

@router.get("/categories")
async def list_categories(conn: asyncpg.Connection = Depends(get_db)):
    rows = await conn.fetch("SELECT * FROM servicedesk_categories ORDER BY name")
    return [dict(r) for r in rows]

@router.get("/tickets")
async def list_tickets(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
    conn: asyncpg.Connection = Depends(get_db)
):
    conditions, params = [], []
    if status:
        params.append(status); conditions.append(f"t.status = ${len(params)}")
    if priority:
        params.append(priority); conditions.append(f"t.priority = ${len(params)}")
    params.append(limit)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    rows = await conn.fetch(f"""
        SELECT t.id, t.ticket_number, t.customer_id, c.name AS customer_name,
               t.subject, t.status, t.priority, t.channel, t.assigned_to,
               t.created_at, t.updated_at, t.resolved_at
        FROM servicedesk_tickets t JOIN customers c ON c.id = t.customer_id
        {where} ORDER BY t.created_at DESC LIMIT ${len(params)}
    """, *params)
    return [serialize_dates(dict(r)) for r in rows]

@router.get("/tickets/open")
async def get_open_tickets(conn: asyncpg.Connection = Depends(get_db)):
    rows = await conn.fetch("""
        SELECT t.id, t.ticket_number, t.customer_id, c.name AS customer_name,
               t.subject, t.status, t.priority, t.channel, t.created_at, t.updated_at, t.resolved_at
        FROM servicedesk_tickets t JOIN customers c ON c.id = t.customer_id
        WHERE t.status IN ('open','in_progress')
        ORDER BY CASE t.priority WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END
    """)
    return [serialize_dates(dict(r)) for r in rows]

@router.get("/tickets/customer/{customer_id}")
async def get_customer_tickets(customer_id: int, conn: asyncpg.Connection = Depends(get_db)):
    rows = await conn.fetch("""
        SELECT t.id, t.ticket_number, t.customer_id, c.name AS customer_name,
               t.subject, t.status, t.priority, t.channel, t.created_at, t.updated_at, t.resolved_at
        FROM servicedesk_tickets t JOIN customers c ON c.id = t.customer_id
        WHERE t.customer_id = $1 ORDER BY t.created_at DESC
    """, customer_id)
    return [serialize_dates(dict(r)) for r in rows]

@router.get("/tickets/{ticket_number}")
async def get_ticket(ticket_number: str, conn: asyncpg.Connection = Depends(get_db)):
    return await fetch_ticket(conn, ticket_number)

@router.post("/tickets", status_code=201)
async def create_ticket(body: CreateTicketRequest, conn: asyncpg.Connection = Depends(get_db)):
    cust = await conn.fetchrow("SELECT id FROM customers WHERE id = $1", body.customer_id)
    if not cust:
        raise HTTPException(status_code=404, detail=f"Customer {body.customer_id} not found")
    count = await conn.fetchval("SELECT COUNT(*) FROM servicedesk_tickets")
    ticket_number = f"TKT-{datetime.now().year}-{(count + 1):05d}"
    ticket_id = await conn.fetchval("""
        INSERT INTO servicedesk_tickets
            (ticket_number, customer_id, category_id, invoice_id, anomaly_id,
             subject, description, status, priority, channel)
        VALUES ($1,$2,$3,$4,$5,$6,$7,'open',$8,$9) RETURNING id
    """, ticket_number, body.customer_id, body.category_id,
         body.invoice_id, body.anomaly_id,
         body.subject, body.description, body.priority, body.channel)
    await conn.execute("""
        INSERT INTO servicedesk_ticket_status_history (ticket_id, new_status, changed_by)
        VALUES ($1,'open','system')
    """, ticket_id)
    return await fetch_ticket(conn, ticket_number)

@router.put("/tickets/{ticket_number}/status")
async def update_ticket_status(
    ticket_number: str, body: UpdateTicketStatusRequest,
    conn: asyncpg.Connection = Depends(get_db)
):
    row = await conn.fetchrow(
        "SELECT id, status FROM servicedesk_tickets WHERE ticket_number = $1", ticket_number)
    if not row:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_number} not found")
    resolved_at = datetime.utcnow() if body.status in ("resolved", "closed") else None
    await conn.execute("""
        UPDATE servicedesk_tickets
        SET status=$1, resolution=$2, updated_at=NOW(), resolved_at=$3
        WHERE ticket_number=$4
    """, body.status, body.resolution, resolved_at, ticket_number)
    await conn.execute("""
        INSERT INTO servicedesk_ticket_status_history (ticket_id, old_status, new_status, changed_by, notes)
        VALUES ($1,$2,$3,'system',$4)
    """, row["id"], row["status"], body.status, body.notes)
    return await fetch_ticket(conn, ticket_number)

@router.post("/tickets/{ticket_number}/comments", status_code=201)
async def add_comment(
    ticket_number: str, body: AddCommentRequest,
    conn: asyncpg.Connection = Depends(get_db)
):
    ticket = await conn.fetchrow(
        "SELECT id FROM servicedesk_tickets WHERE ticket_number = $1", ticket_number)
    if not ticket:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_number} not found")
    await conn.execute("""
        INSERT INTO servicedesk_ticket_comments (ticket_id, author, comment, is_internal)
        VALUES ($1,$2,$3,$4)
    """, ticket["id"], body.author, body.comment, body.is_internal)
    await conn.execute("UPDATE servicedesk_tickets SET updated_at=NOW() WHERE id=$1", ticket["id"])
    return await fetch_ticket(conn, ticket_number)

@router.get("/metrics")
async def get_sd_metrics(conn: asyncpg.Connection = Depends(get_db)):
    today = date.today()
    return {
        "tickets_created_today": int(await conn.fetchval(
            "SELECT COUNT(*) FROM servicedesk_tickets WHERE DATE(created_at)=$1", today) or 0),
        "tickets_resolved_today": int(await conn.fetchval(
            "SELECT COUNT(*) FROM servicedesk_tickets WHERE status='resolved' AND DATE(resolved_at)=$1", today) or 0),
        "tickets_open": int(await conn.fetchval(
            "SELECT COUNT(*) FROM servicedesk_tickets WHERE status IN ('open','in_progress')") or 0),
        "tickets_critical_open": int(await conn.fetchval(
            "SELECT COUNT(*) FROM servicedesk_tickets WHERE status='open' AND priority='critical'") or 0),
    }
