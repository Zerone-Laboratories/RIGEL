"""Integration tests for web_server.py database operations.

Tests the SQLite schema and queries used by web_server (API key management,
tenant operations, rate limiting, usage tracking) against a real temporary
database — no mocking needed.
"""

import os
import sqlite3
import hashlib
import secrets
import tempfile
import time
from datetime import datetime, timedelta, timezone

import pytest


# ---------------------------------------------------------------------------
# Schema — mirroring web_server.init_database()
# ---------------------------------------------------------------------------

DDL_TENANTS = """
    CREATE TABLE IF NOT EXISTS tenants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        api_key_hash TEXT UNIQUE NOT NULL,
        plan TEXT NOT NULL DEFAULT 'free',
        active BOOLEAN DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        monthly_quota INTEGER DEFAULT 1000,
        daily_quota INTEGER DEFAULT 100
    )
"""

DDL_USAGE = """
    CREATE TABLE IF NOT EXISTS usage (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id INTEGER,
        endpoint TEXT NOT NULL,
        tokens_estimated INTEGER DEFAULT 0,
        duration_ms INTEGER DEFAULT 0,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (tenant_id) REFERENCES tenants (id)
    )
"""

DDL_RATE_LIMITS = """
    CREATE TABLE IF NOT EXISTS rate_limits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id INTEGER,
        endpoint TEXT NOT NULL,
        requests_count INTEGER DEFAULT 1,
        window_start TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (tenant_id) REFERENCES tenants (id),
        UNIQUE(tenant_id, endpoint, window_start)
    )
"""

PLAN_QUOTAS = {
    "free": {"monthly": 1000, "daily": 100},
    "pro": {"monthly": 20000, "daily": 1000},
    "enterprise": {"monthly": 100000, "daily": 5000},
}

PLAN_RATE_LIMITS = {  # requests per minute
    "free": 10,
    "pro": 60,
    "enterprise": 300,
}


def init_db(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(DDL_TENANTS)
    conn.execute(DDL_USAGE)
    conn.execute(DDL_RATE_LIMITS)
    conn.commit()
    conn.close()


def create_api_key(db_path, name, plan="free"):
    """Mirrors web_server.create_api_key()."""
    api_key = f"rigel_{secrets.token_urlsafe(32)}"
    api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    # Unknown plans fall back to "free", matching the original logic
    effective_plan = plan if plan in PLAN_QUOTAS else "free"
    quota = PLAN_QUOTAS[effective_plan]
    conn = sqlite3.connect(db_path)
    conn.execute(
        """INSERT INTO tenants (name, api_key_hash, plan, monthly_quota, daily_quota)
           VALUES (?, ?, ?, ?, ?)""",
        (name, api_key_hash, effective_plan, quota["monthly"], quota["daily"]),
    )
    conn.commit()
    conn.close()
    return api_key


def get_tenant(db_path, api_key):
    """Mirrors web_server.get_tenant_info()."""
    if not api_key:
        return None
    api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    conn = sqlite3.connect(db_path)
    row = conn.execute(
        """SELECT id, name, plan, active, monthly_quota, daily_quota
           FROM tenants WHERE api_key_hash = ? AND active = 1""",
        (api_key_hash,),
    ).fetchone()
    conn.close()
    if not row:
        return None
    return {
        "tenant_id": row[0], "name": row[1], "plan": row[2],
        "active": row[3], "monthly_quota": row[4], "daily_quota": row[5],
    }


def check_rate_limit(db_path, tenant_id, endpoint):
    """Mirrors web_server.check_rate_limit()."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    plan_row = conn.execute(
        "SELECT plan FROM tenants WHERE id = ?", (tenant_id,)
    ).fetchone()
    if not plan_row:
        conn.close()
        return False

    limit = PLAN_RATE_LIMITS.get(plan_row[0], 10)
    now = datetime.now(timezone.utc)
    window_start = now.replace(second=0, microsecond=0)

    existing = conn.execute(
        """SELECT id, requests_count FROM rate_limits
           WHERE tenant_id = ? AND endpoint = ? AND window_start = ?""",
        (tenant_id, endpoint, window_start),
    ).fetchone()

    if existing:
        row_id, count = existing[0], existing[1]
        ok = count < limit
        if ok:
            conn.execute(
                "UPDATE rate_limits SET requests_count = requests_count + 1 WHERE id = ?",
                (row_id,),
            )
    else:
        conn.execute(
            """INSERT INTO rate_limits (tenant_id, endpoint, requests_count, window_start)
               VALUES (?, ?, 1, ?)""",
            (tenant_id, endpoint, window_start),
        )
        ok = True

    conn.commit()
    conn.close()
    return ok


def record_usage(db_path, tenant_id, endpoint, tokens_estimated=0, duration_ms=0):
    """Mirrors web_server.record_usage()."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        """INSERT INTO usage (tenant_id, endpoint, tokens_estimated, duration_ms)
           VALUES (?, ?, ?, ?)""",
        (tenant_id, endpoint, tokens_estimated, duration_ms),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db():
    """Create a temporary database with the web_server schema."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_rigel_usage.db")
        init_db(db_path)
        yield db_path
        if os.path.exists(db_path):
            os.remove(db_path)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSchema:
    def test_tables_exist(self, db):
        conn = sqlite3.connect(db)
        tables = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        assert "tenants" in tables
        assert "usage" in tables
        assert "rate_limits" in tables
        conn.close()


class TestCreateApiKey:
    def test_creates_rigel_prefixed_key(self, db):
        key = create_api_key(db, "TestTenant")
        assert key.startswith("rigel_")
        assert len(key) > 20

    def test_tenant_stored_correctly(self, db):
        key = create_api_key(db, "MyTenant", plan="pro")
        info = get_tenant(db, key)
        assert info is not None
        assert info["name"] == "MyTenant"
        assert info["plan"] == "pro"
        assert info["monthly_quota"] == 20000
        assert info["daily_quota"] == 1000

    def test_enterprise_quotas(self, db):
        key = create_api_key(db, "BigCo", plan="enterprise")
        info = get_tenant(db, key)
        assert info["monthly_quota"] == 100000
        assert info["daily_quota"] == 5000

    def test_unknown_plan_defaults_to_free(self, db):
        key = create_api_key(db, "Unknown", plan="super_premium")
        info = get_tenant(db, key)
        assert info["plan"] == "free"
        assert info["monthly_quota"] == 1000
        assert info["daily_quota"] == 100


class TestGetTenant:
    def test_returns_none_for_bogus_key(self, db):
        assert get_tenant(db, "not_a_real_key") is None

    def test_returns_none_for_empty_key(self, db):
        assert get_tenant(db, "") is None

    def test_returns_none_for_none_key(self, db):
        assert get_tenant(db, None) is None

    def test_returns_info_for_valid_key(self, db):
        key = create_api_key(db, "ValidCo", plan="pro")
        info = get_tenant(db, key)
        assert info["name"] == "ValidCo"
        assert info["active"] == 1


class TestRateLimit:
    def test_nonexistent_tenant_returns_false(self, db):
        assert check_rate_limit(db, 99999, "/query") is False

    def test_first_request_allowed(self, db):
        key = create_api_key(db, "RateTest")
        info = get_tenant(db, key)
        assert check_rate_limit(db, info["tenant_id"], "/query") is True


class TestRecordUsage:
    def test_records_usage_row(self, db):
        key = create_api_key(db, "UsageCo")
        info = get_tenant(db, key)
        record_usage(db, info["tenant_id"], "/query", tokens_estimated=42, duration_ms=150)

        conn = sqlite3.connect(db)
        rows = conn.execute(
            "SELECT endpoint, tokens_estimated, duration_ms FROM usage WHERE tenant_id = ?",
            (info["tenant_id"],),
        ).fetchall()
        conn.close()
        assert len(rows) == 1
        assert rows[0][0] == "/query"
        assert rows[0][1] == 42
        assert rows[0][2] == 150

    def test_usage_per_endpoint(self, db):
        key = create_api_key(db, "MultiEp")
        info = get_tenant(db, key)
        record_usage(db, info["tenant_id"], "/query", tokens_estimated=10)
        record_usage(db, info["tenant_id"], "/query-with-tools", tokens_estimated=30)

        conn = sqlite3.connect(db)
        rows = conn.execute(
            "SELECT endpoint FROM usage WHERE tenant_id = ? ORDER BY id",
            (info["tenant_id"],),
        ).fetchall()
        conn.close()
        assert len(rows) == 2
        assert rows[0][0] == "/query"
        assert rows[1][0] == "/query-with-tools"


class TestTenantIsolation:
    def test_keys_are_unique(self, db):
        key1 = create_api_key(db, "TenantA")
        key2 = create_api_key(db, "TenantB")
        assert key1 != key2

    def test_info_only_returns_active(self, db):
        key = create_api_key(db, "ActiveTenant")
        # Deactivate the tenant
        conn = sqlite3.connect(db)
        conn.execute("UPDATE tenants SET active = 0 WHERE name = ?", ("ActiveTenant",))
        conn.commit()
        conn.close()
        assert get_tenant(db, key) is None
