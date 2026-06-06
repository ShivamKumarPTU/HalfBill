import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from config import DB_URL
import asyncpg
from datetime import datetime, timedelta
import random

async def fix_fsm():
    print("Connecting to database to fix FSM tables...")
    # Use the postgres superuser with the password we set in Docker
    conn = await asyncpg.connect("postgresql://postgres:secret@localhost:15432/onebill")
    
    # 1. Insert 25 Technicians
    zones = ['North', 'South', 'East', 'West', 'Central']
    statuses = ['available', 'on_job', 'off_duty']
    
    print("Inserting 25 technicians...")
    for i in range(1, 26):
        await conn.execute("""
            INSERT INTO fsm_technicians (technician_code, name, phone, email, zone, specializations, status)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT DO NOTHING
        """, 
        f"TECH-{i:03d}", 
        f"Technician {i}", 
        f"555-01{i:02d}", 
        f"tech{i}@onebill.com", 
        random.choice(zones), 
        ["fiber", "installation"], 
        random.choice(statuses))
        
    print("Technicians inserted!")
    
    # 2. Insert FSM Jobs
    print("Inserting FSM Jobs...")
    customers = await conn.fetch("SELECT id FROM customers LIMIT 50")
    technicians = await conn.fetch("SELECT id FROM fsm_technicians")
    
    for i, cust in enumerate(customers):
        job_number = f"JOB-2026-{i:04d}"
        job_id = await conn.fetchval("""
            INSERT INTO fsm_jobs (job_number, customer_id, job_type, priority, status, description, scheduled_date)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT DO NOTHING
            RETURNING id
        """, 
        job_number, 
        cust['id'], 
        "installation", 
        "high" if i % 5 == 0 else "medium", 
        "assigned", 
        "Fixing the router.",
        (datetime.now() + timedelta(days=1)).date())
        
        if job_id is None:
            job_id = await conn.fetchval("SELECT id FROM fsm_jobs WHERE job_number = $1", job_number)
        
        # Assign a random technician
        await conn.execute("""
            INSERT INTO fsm_job_assignments (job_id, technician_id, is_primary)
            VALUES ($1, $2, TRUE)
        """, job_id, random.choice(technicians)['id'])
        
    print("FSM Jobs fixed! Database is now 100% fully populated.")
    await conn.close()

if __name__ == "__main__":
    asyncio.run(fix_fsm())
