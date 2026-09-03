"""SQLite-backed persistence for users, API keys, tenants and prediction audit log.

SQLite (not Postgres) is used deliberately: it needs zero external infra to run,
which matters for a portfolio project people will actually try to run locally,
while still being a real persistence layer instead of process-memory dicts that
reset on every restart.
"""
import hashlib
import os
import secrets
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.config import DATABASE_PATH, SEED_DEMO_DATA

_lock = threading.Lock()


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DATABASE_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def get_conn():
    with _lock:
        conn = _connect()
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()


def init_db():
    """Create tables if they don't exist, and seed demo data once."""
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS tenants (
                tenant_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL,
                tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id),
                roles TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS api_keys (
                api_key TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id),
                permissions TEXT NOT NULL,
                rate_limit INTEGER NOT NULL DEFAULT 1000,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id TEXT NOT NULL,
                customer_id INTEGER NOT NULL,
                model_version TEXT NOT NULL,
                risk_score REAL NOT NULL,
                risk_class INTEGER NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )

    if SEED_DEMO_DATA:
        _seed_demo_data()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def _seed_demo_data():
    """Insert demo tenants/users/keys only if the DB is empty. Clearly demo-only
    credentials - never used as a real default in a deployed instance."""
    with get_conn() as conn:
        existing = conn.execute("SELECT COUNT(*) AS c FROM tenants").fetchone()["c"]
        if existing > 0:
            return

        for tenant_id, name in [("admin", "Admin"), ("tenant_1", "Demo Tenant 1"), ("tenant_2", "Demo Tenant 2")]:
            conn.execute(
                "INSERT OR IGNORE INTO tenants (tenant_id, name, created_at) VALUES (?, ?, ?)",
                (tenant_id, name, _now()),
            )

        conn.execute(
            "INSERT OR IGNORE INTO users (username, password_hash, tenant_id, roles, is_active, created_at) "
            "VALUES (?, ?, ?, ?, 1, ?)",
            ("admin", _hash_password("admin123"), "admin", "admin,user", _now()),
        )
        conn.execute(
            "INSERT OR IGNORE INTO users (username, password_hash, tenant_id, roles, is_active, created_at) "
            "VALUES (?, ?, ?, ?, 1, ?)",
            ("user1", _hash_password("user123"), "tenant_1", "user", _now()),
        )

        conn.execute(
            "INSERT OR IGNORE INTO api_keys (api_key, tenant_id, permissions, rate_limit, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            ("demo-api-key-tenant1", "tenant_1", "read,predict", 1000, _now()),
        )
        conn.execute(
            "INSERT OR IGNORE INTO api_keys (api_key, tenant_id, permissions, rate_limit, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            ("demo-api-key-tenant2", "tenant_2", "read,predict,admin", 5000, _now()),
        )


# --- Users -----------------------------------------------------------------

def get_user(username: str) -> Optional[Dict[str, Any]]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        return dict(row) if row else None


def verify_password(plain_password: str, password_hash: str) -> bool:
    return _hash_password(plain_password) == password_hash


def create_user(username: str, password: str, tenant_id: str, roles: List[str]) -> Dict[str, Any]:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO tenants (tenant_id, name, created_at) VALUES (?, ?, ?) "
            "ON CONFLICT(tenant_id) DO NOTHING",
            (tenant_id, tenant_id, _now()),
        )
        conn.execute(
            "INSERT INTO users (username, password_hash, tenant_id, roles, is_active, created_at) "
            "VALUES (?, ?, ?, ?, 1, ?)",
            (username, _hash_password(password), tenant_id, ",".join(roles), _now()),
        )
    return get_user(username)


# --- API keys ----------------------------------------------------------------

def get_api_key(api_key: str) -> Optional[Dict[str, Any]]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM api_keys WHERE api_key = ?", (api_key,)).fetchone()
        return dict(row) if row else None


def create_api_key(tenant_id: str, permissions: Optional[List[str]] = None, rate_limit: int = 1000) -> str:
    api_key = f"rsk_{secrets.token_urlsafe(32)}"
    perms = permissions or ["read", "predict"]
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO api_keys (api_key, tenant_id, permissions, rate_limit, created_at) VALUES (?, ?, ?, ?, ?)",
            (api_key, tenant_id, ",".join(perms), rate_limit, _now()),
        )
    return api_key


# --- Predictions audit log ---------------------------------------------------

def record_prediction(tenant_id: str, customer_id: int, model_version: str, risk_score: float, risk_class: int):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO predictions (tenant_id, customer_id, model_version, risk_score, risk_class, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (tenant_id, customer_id, model_version, risk_score, risk_class, _now()),
        )


def get_predictions_for_tenant(tenant_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM predictions WHERE tenant_id = ? ORDER BY id DESC LIMIT ?",
            (tenant_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]
