from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, date
import asyncpg
import json

from infra.shared.db import get_db

router = APIRouter()

# ── Pydantic Models ───────────────────────────────────────────────────

class CreateJobRequest(BaseModel):
    customer_id: int
    ticket_id: Optional[int] = None
    invoice_id: Optional[int] = None
    job_type: str   # installation, repair, maintenance, equipment_swap, inspection, disconnection
    priority: str = "medium"
    description: str
    address_line1: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None
    scheduled_date: Optional[date] = None
    scheduled_start_time: Optional[str] = None
    scheduled_end_time: Optional[str] = None

class AssignTechnicianRequest(BaseModel):
    technician_id: int

class UpdateJobStatusRequest(BaseModel):
    status: str
    completion_notes: Optional[str] = None
    parts_used: Optional[dict] = None


# ── Helpers ───────────────────────────────────────────────────────────

def serialize_job(d: dict) -> dict:
    for field in ("scheduled_date", "actual_start", "actual_end", "created_at", "updated_at"):
        if d.get(field):
            d[field] = str(d[field])
    if isinstance(d.get("parts_used"), str):
        try:
            d["parts_used"] = json.loads(d["parts_used"])
        except Exception:
            pass
    return d

async def fetch_job(conn, job_number: str):
    row = await conn.fetchrow("""
        SELECT j.id, j.job_number, j.customer_id, c.name AS customer_name,
               j.ticket_id, j.invoice_id, j.job_type, j.status, j.priority,
               j.description, j.address_line1, j.city, j.state, j.zip,
               j.scheduled_date, j.scheduled_start_time, j.scheduled_end_time,
               j.actual_start, j.actual_end, j.completion_notes, j.parts_used,
               j.created_at, j.updated_at
        FROM fsm_jobs j JOIN customers c ON c.id = j.customer_id
        WHERE j.job_number = $1
    """, job_number)
    if not row:
        raise HTTPException(status_code=404, detail=f"Job {job_number} not found")
    job = serialize_job(dict(row))

    # Fetch assignment
    assignment = await conn.fetchrow("""
        SELECT a.technician_id, t.name AS technician_name, t.phone AS technician_phone,
               a.assigned_at, a.is_primary
        FROM fsm_job_assignments a JOIN fsm_technicians t ON t.id = a.technician_id
        WHERE a.job_id = $1 AND a.is_primary = TRUE
    """, job["id"])
    job["assignment"] = None
    if assignment:
        d = dict(assignment)
        d["assigned_at"] = str(d["assigned_at"])
        job["assignment"] = d
    return job


# ── Technicians ───────────────────────────────────────────────────────

@router.get("/technicians")
async def list_technicians(conn: asyncpg.Connection = Depends(get_db)):
    rows = await conn.fetch("""
        SELECT id, technician_code, name, email, phone, specializations,
               status, zone, jobs_completed, rating
        FROM fsm_technicians ORDER BY zone, name
    """)
    return [dict(r) for r in rows]

@router.get("/technicians/available")
async def get_available_technicians(
    zone: Optional[str] = None,
    specialization: Optional[str] = None,
    conn: asyncpg.Connection = Depends(get_db)
):
    conditions = ["status = 'available'"]
    params = []
    if zone:
        params.append(zone); conditions.append(f"zone = ${len(params)}")
    if specialization:
        params.append(specialization); conditions.append(f"specializations @> ARRAY[${len(params)}]")
    where = "WHERE " + " AND ".join(conditions)
    rows = await conn.fetch(f"""
        SELECT id, technician_code, name, email, phone, specializations,
               status, zone, jobs_completed, rating
        FROM fsm_technicians {where} ORDER BY rating DESC
    """, *params)
    return [dict(r) for r in rows]

@router.get("/technicians/{technician_id}")
async def get_technician(technician_id: int, conn: asyncpg.Connection = Depends(get_db)):
    row = await conn.fetchrow("""
        SELECT id, technician_code, name, email, phone, specializations,
               status, zone, jobs_completed, rating
        FROM fsm_technicians WHERE id = $1
    """, technician_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Technician {technician_id} not found")
    return dict(row)

@router.get("/technicians/{technician_id}/schedule")
async def get_technician_schedule(technician_id: int, conn: asyncpg.Connection = Depends(get_db)):
    tech = await conn.fetchrow("""
        SELECT id, technician_code, name, email, phone, specializations,
               status, zone, jobs_completed, rating
        FROM fsm_technicians WHERE id = $1
    """, technician_id)
    if not tech:
        raise HTTPException(status_code=404, detail=f"Technician {technician_id} not found")
    slots = await conn.fetch("""
        SELECT schedule_date, start_time, end_time, is_available
        FROM fsm_technician_schedules
        WHERE technician_id = $1 AND schedule_date >= CURRENT_DATE
          AND schedule_date <= CURRENT_DATE + INTERVAL '14 days'
        ORDER BY schedule_date
    """, technician_id)
    return {
        "technician": dict(tech),
        "schedule": [
            {**dict(s), "schedule_date": str(s["schedule_date"]),
             "start_time": str(s["start_time"]), "end_time": str(s["end_time"])}
            for s in slots
        ]
    }


# ── Jobs ──────────────────────────────────────────────────────────────

@router.get("/jobs")
async def list_jobs(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
    conn: asyncpg.Connection = Depends(get_db)
):
    conditions, params = [], []
    if status:
        params.append(status); conditions.append(f"j.status = ${len(params)}")
    if priority:
        params.append(priority); conditions.append(f"j.priority = ${len(params)}")
    params.append(limit)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    rows = await conn.fetch(f"""
        SELECT j.id, j.job_number, j.customer_id, c.name AS customer_name,
               j.job_type, j.status, j.priority, j.description,
               j.scheduled_date, j.created_at, j.updated_at
        FROM fsm_jobs j JOIN customers c ON c.id = j.customer_id
        {where} ORDER BY j.created_at DESC LIMIT ${len(params)}
    """, *params)
    return [serialize_job(dict(r)) for r in rows]

@router.get("/jobs/pending")
async def get_pending_jobs(conn: asyncpg.Connection = Depends(get_db)):
    rows = await conn.fetch("""
        SELECT j.id, j.job_number, j.customer_id, c.name AS customer_name,
               j.job_type, j.status, j.priority, j.description, j.scheduled_date
        FROM fsm_jobs j JOIN customers c ON c.id = j.customer_id
        WHERE j.status = 'pending'
        ORDER BY CASE j.priority WHEN 'emergency' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END
    """)
    return [serialize_job(dict(r)) for r in rows]

@router.get("/jobs/scheduled")
async def get_scheduled_jobs(
    scheduled_date: date = Query(...),
    conn: asyncpg.Connection = Depends(get_db)
):
    rows = await conn.fetch("""
        SELECT j.id, j.job_number, j.customer_id, c.name AS customer_name,
               j.job_type, j.status, j.priority, j.description, j.scheduled_date
        FROM fsm_jobs j JOIN customers c ON c.id = j.customer_id
        WHERE j.scheduled_date = $1 ORDER BY j.scheduled_start_time
    """, scheduled_date)
    return [serialize_job(dict(r)) for r in rows]

@router.get("/jobs/customer/{customer_id}")
async def get_customer_jobs(customer_id: int, conn: asyncpg.Connection = Depends(get_db)):
    rows = await conn.fetch("""
        SELECT j.id, j.job_number, j.customer_id, c.name AS customer_name,
               j.job_type, j.status, j.priority, j.description, j.scheduled_date
        FROM fsm_jobs j JOIN customers c ON c.id = j.customer_id
        WHERE j.customer_id = $1 ORDER BY j.created_at DESC
    """, customer_id)
    return [serialize_job(dict(r)) for r in rows]

@router.get("/jobs/{job_number}")
async def get_job(job_number: str, conn: asyncpg.Connection = Depends(get_db)):
    return await fetch_job(conn, job_number)

@router.post("/jobs", status_code=201)
async def create_job(body: CreateJobRequest, conn: asyncpg.Connection = Depends(get_db)):
    cust = await conn.fetchrow(
        "SELECT id, address_line1, city, state, zip FROM customers WHERE id = $1", body.customer_id)
    if not cust:
        raise HTTPException(status_code=404, detail=f"Customer {body.customer_id} not found")

    # Use customer address as fallback
    addr = body.address_line1 or cust["address_line1"]
    city = body.city or cust["city"]
    state = body.state or cust["state"]
    zip_code = body.zip or cust["zip"]

    count = await conn.fetchval("SELECT COUNT(*) FROM fsm_jobs")
    job_number = f"JOB-{datetime.now().year}-{(count + 1):05d}"

    job_id = await conn.fetchval("""
        INSERT INTO fsm_jobs
            (job_number, customer_id, ticket_id, invoice_id, job_type, priority,
             status, description, address_line1, city, state, zip,
             scheduled_date, scheduled_start_time, scheduled_end_time)
        VALUES ($1,$2,$3,$4,$5,$6,'pending',$7,$8,$9,$10,$11,$12,$13,$14)
        RETURNING id
    """, job_number, body.customer_id, body.ticket_id, body.invoice_id,
         body.job_type, body.priority, body.description,
         addr, city, state, zip_code,
         body.scheduled_date, body.scheduled_start_time, body.scheduled_end_time)

    return await fetch_job(conn, job_number)

@router.post("/jobs/{job_number}/assign")
async def assign_technician(
    job_number: str, body: AssignTechnicianRequest,
    conn: asyncpg.Connection = Depends(get_db)
):
    job = await conn.fetchrow(
        "SELECT id, status FROM fsm_jobs WHERE job_number = $1", job_number)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_number} not found")

    tech = await conn.fetchrow(
        "SELECT id, status FROM fsm_technicians WHERE id = $1", body.technician_id)
    if not tech:
        raise HTTPException(status_code=404, detail=f"Technician {body.technician_id} not found")
    if tech["status"] != "available":
        raise HTTPException(
            status_code=409, detail=f"Technician {body.technician_id} is not available (status: {tech['status']})")

    # Remove old assignment if any
    await conn.execute("DELETE FROM fsm_job_assignments WHERE job_id = $1", job["id"])

    await conn.execute("""
        INSERT INTO fsm_job_assignments (job_id, technician_id, is_primary)
        VALUES ($1,$2,TRUE)
    """, job["id"], body.technician_id)

    await conn.execute(
        "UPDATE fsm_jobs SET status='assigned', updated_at=NOW() WHERE id=$1", job["id"])
    await conn.execute(
        "UPDATE fsm_technicians SET status='on_job' WHERE id=$1", body.technician_id)

    return await fetch_job(conn, job_number)

@router.put("/jobs/{job_number}/status")
async def update_job_status(
    job_number: str, body: UpdateJobStatusRequest,
    conn: asyncpg.Connection = Depends(get_db)
):
    job = await conn.fetchrow(
        "SELECT id, status FROM fsm_jobs WHERE job_number = $1", job_number)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_number} not found")

    updates = {"status": body.status}
    if body.status == "in_progress":
        updates["actual_start"] = datetime.utcnow()
    elif body.status == "completed":
        updates["actual_end"] = datetime.utcnow()
        updates["completion_notes"] = body.completion_notes
        if body.parts_used:
            updates["parts_used"] = json.dumps(body.parts_used)
        # Free technician
        assignment = await conn.fetchrow(
            "SELECT technician_id FROM fsm_job_assignments WHERE job_id=$1 AND is_primary=TRUE", job["id"])
        if assignment:
            await conn.execute(
                "UPDATE fsm_technicians SET status='available', jobs_completed=jobs_completed+1 WHERE id=$1",
                assignment["technician_id"])
    elif body.status in ("cancelled", "no_show"):
        assignment = await conn.fetchrow(
            "SELECT technician_id FROM fsm_job_assignments WHERE job_id=$1 AND is_primary=TRUE", job["id"])
        if assignment:
            await conn.execute(
                "UPDATE fsm_technicians SET status='available' WHERE id=$1",
                assignment["technician_id"])

    await conn.execute("""
        UPDATE fsm_jobs SET status=$1, actual_start=$2, actual_end=$3,
               completion_notes=$4, updated_at=NOW()
        WHERE id=$5
    """, updates.get("status"), updates.get("actual_start"),
         updates.get("actual_end"), updates.get("completion_notes"), job["id"])

    return await fetch_job(conn, job_number)


# ── Metrics ───────────────────────────────────────────────────────────

@router.get("/metrics")
async def get_fsm_metrics(conn: asyncpg.Connection = Depends(get_db)):
    today = date.today()
    scheduled_today = int(await conn.fetchval(
        "SELECT COUNT(*) FROM fsm_jobs WHERE scheduled_date=$1", today) or 0)
    completed_today = int(await conn.fetchval(
        "SELECT COUNT(*) FROM fsm_jobs WHERE status='completed' AND DATE(actual_end)=$1", today) or 0)
    in_progress = int(await conn.fetchval(
        "SELECT COUNT(*) FROM fsm_jobs WHERE status='in_progress'") or 0)
    pending = int(await conn.fetchval(
        "SELECT COUNT(*) FROM fsm_jobs WHERE status='pending'") or 0)
    total_techs = int(await conn.fetchval("SELECT COUNT(*) FROM fsm_technicians") or 0)
    on_job = int(await conn.fetchval(
        "SELECT COUNT(*) FROM fsm_technicians WHERE status='on_job'") or 0)
    utilisation = round((on_job / max(total_techs, 1)) * 100, 1)

    return {
        "jobs_scheduled_today": scheduled_today,
        "jobs_completed_today": completed_today,
        "jobs_in_progress": in_progress,
        "jobs_pending_assignment": pending,
        "technician_utilisation_pct": utilisation,
        "completion_rate_7d_pct": 0.0,  # Extended metric — requires historical window
    }
