"""Acceso a PostgreSQL (Supabase) con pool de conexiones."""
import atexit
import os
from contextlib import contextmanager

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/unab")

_pool: ConnectionPool | None = None


def pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            DATABASE_URL, min_size=1, max_size=5, open=True,
            kwargs={"row_factory": dict_row, "options": "-c search_path=academico,public,extensions",
                    "prepare_threshold": None},  # compatible con el pooler de Supabase
        )
        atexit.register(_pool.close)
    return _pool


@contextmanager
def cursor():
    with pool().connection() as conn:
        with conn.cursor() as cur:
            yield cur


def fetch_all(sql: str, params=None) -> list[dict]:
    with cursor() as cur:
        cur.execute(sql, params or ())
        return [_clean(r) for r in cur.fetchall()]


def fetch_one(sql: str, params=None) -> dict | None:
    rows = fetch_all(sql, params)
    return rows[0] if rows else None


def execute(sql: str, params=None) -> int:
    with cursor() as cur:
        cur.execute(sql, params or ())
        return cur.rowcount


def _clean(row: dict) -> dict:
    """Convierte Decimal/fechas a tipos serializables en JSON."""
    out = {}
    for k, v in row.items():
        if v is None or isinstance(v, (str, int, float, bool, list, dict)):
            out[k] = v
        elif v.__class__.__name__ == "Decimal":
            out[k] = float(v)
        else:
            out[k] = str(v)
    return out
