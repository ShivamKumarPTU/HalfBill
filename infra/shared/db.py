import asyncpg
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from config import DB_URL

_pool = None

async def get_pool():
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DB_URL, min_size=2, max_size=10)
    return _pool

async def get_db():
    """Dependency for FastAPI routes. Yields a connection from the pool."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        yield conn
