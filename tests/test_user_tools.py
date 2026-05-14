"""Integration tests for user_tools.py database operations.

Tests the SQLite schema and queries used by user_tools (user-defined tools
and RAG data management) against a real temporary database.
"""

import os
import sqlite3
import tempfile
import pytest


# ---------------------------------------------------------------------------
# Schema — mirroring user_tools.init_tools_database()
# ---------------------------------------------------------------------------

DDL_USER_TOOLS = """
    CREATE TABLE IF NOT EXISTS user_tools (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id INTEGER NOT NULL,
        tool_name TEXT NOT NULL,
        tool_code TEXT NOT NULL,
        tool_description TEXT DEFAULT '',
        tool_args TEXT DEFAULT '{}',
        active BOOLEAN DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(tenant_id, tool_name)
    )
"""

DDL_RAG_DATA = """
    CREATE TABLE IF NOT EXISTS rag_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id INTEGER NOT NULL,
        data_name TEXT NOT NULL,
        data_type TEXT DEFAULT 'text',
        data_content TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
"""


def init_db(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(DDL_USER_TOOLS)
    conn.execute(DDL_RAG_DATA)
    conn.commit()
    conn.close()


def insert_tool(db_path, tenant_id, name, code, description="", args="{}"):
    conn = sqlite3.connect(db_path)
    conn.execute(
        """INSERT INTO user_tools (tenant_id, tool_name, tool_code, tool_description, tool_args)
           VALUES (?, ?, ?, ?, ?)""",
        (tenant_id, name, code, description, args),
    )
    conn.commit()
    conn.close()


def insert_rag(db_path, tenant_id, name, content, data_type="text"):
    conn = sqlite3.connect(db_path)
    conn.execute(
        """INSERT INTO rag_data (tenant_id, data_name, data_type, data_content)
           VALUES (?, ?, ?, ?)""",
        (tenant_id, name, data_type, content),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_rigel_tools.db")
        init_db(db_path)
        yield db_path
        if os.path.exists(db_path):
            os.remove(db_path)


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------

class TestSchema:
    def test_tables_exist(self, db):
        conn = sqlite3.connect(db)
        tables = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        assert "user_tools" in tables
        assert "rag_data" in tables
        conn.close()

    def test_user_tools_columns(self, db):
        conn = sqlite3.connect(db)
        cols = {row[1] for row in conn.execute("PRAGMA table_info(user_tools)")}
        expected = {"id", "tenant_id", "tool_name", "tool_code",
                    "tool_description", "tool_args", "active", "created_at"}
        assert expected.issubset(cols)
        conn.close()

    def test_rag_data_columns(self, db):
        conn = sqlite3.connect(db)
        cols = {row[1] for row in conn.execute("PRAGMA table_info(rag_data)")}
        expected = {"id", "tenant_id", "data_name", "data_type",
                    "data_content", "created_at"}
        assert expected.issubset(cols)
        conn.close()

    def test_tool_name_unique_per_tenant(self, db):
        """Each tenant can have only one tool with a given name."""
        insert_tool(db, 1, "my_tool", "def run(): pass")
        with pytest.raises(sqlite3.IntegrityError):
            insert_tool(db, 1, "my_tool", "def run(): return 1")

    def test_tool_name_can_be_reused_by_different_tenant(self, db):
        """Different tenants can use the same tool name."""
        insert_tool(db, 1, "shared_name", "code1")
        insert_tool(db, 2, "shared_name", "code2")  # should not raise


# ---------------------------------------------------------------------------
# Tool CRUD tests
# ---------------------------------------------------------------------------

class TestToolCRUD:
    def test_insert_and_read(self, db):
        insert_tool(db, 1, "echo", "def run():\n    return 'echo'",
                    description="Echo tool", args='{"msg": "str"}')

        conn = sqlite3.connect(db)
        row = conn.execute(
            "SELECT tenant_id, tool_name, tool_code, tool_description, tool_args, active "
            "FROM user_tools WHERE tool_name = ?", ("echo",)
        ).fetchone()
        conn.close()

        assert row[0] == 1
        assert row[1] == "echo"
        assert "def run()" in row[2]
        assert row[3] == "Echo tool"
        assert row[4] == '{"msg": "str"}'
        assert row[5] == 1  # active

    def test_default_active_is_true(self, db):
        insert_tool(db, 1, "default_active", "pass")
        conn = sqlite3.connect(db)
        active = conn.execute(
            "SELECT active FROM user_tools WHERE tool_name = ?", ("default_active",)
        ).fetchone()[0]
        conn.close()
        assert active == 1

    def test_tenant_isolation(self, db):
        insert_tool(db, 1, "tool_a", "code_a")
        insert_tool(db, 2, "tool_b", "code_b")
        insert_tool(db, 1, "tool_c", "code_c")

        conn = sqlite3.connect(db)
        t1_tools = [row[0] for row in conn.execute(
            "SELECT tool_name FROM user_tools WHERE tenant_id = 1 ORDER BY tool_name"
        ).fetchall()]
        t2_tools = [row[0] for row in conn.execute(
            "SELECT tool_name FROM user_tools WHERE tenant_id = 2"
        ).fetchall()]
        conn.close()

        assert t1_tools == ["tool_a", "tool_c"]
        assert t2_tools == ["tool_b"]

    def test_deactivate_tool(self, db):
        insert_tool(db, 1, "deactivable", "code")
        conn = sqlite3.connect(db)
        conn.execute(
            "UPDATE user_tools SET active = 0 WHERE tool_name = ?", ("deactivable",)
        )
        conn.commit()
        active = conn.execute(
            "SELECT active FROM user_tools WHERE tool_name = ?", ("deactivable",)
        ).fetchone()[0]
        conn.close()
        assert active == 0


# ---------------------------------------------------------------------------
# RAG data CRUD tests
# ---------------------------------------------------------------------------

class TestRagDataCRUD:
    def test_insert_and_read_text(self, db):
        insert_rag(db, 1, "notes", "These are some text notes.", data_type="text")

        conn = sqlite3.connect(db)
        row = conn.execute(
            "SELECT tenant_id, data_name, data_type, data_content FROM rag_data WHERE data_name = ?",
            ("notes",),
        ).fetchone()
        conn.close()

        assert row[0] == 1
        assert row[1] == "notes"
        assert row[2] == "text"
        assert row[3] == "These are some text notes."

    def test_insert_pdf_type(self, db):
        insert_rag(db, 1, "manual", "PDF content page 1\nPDF content page 2",
                   data_type="pdf")

        conn = sqlite3.connect(db)
        row = conn.execute(
            "SELECT data_type, data_content FROM rag_data WHERE data_name = ?",
            ("manual",),
        ).fetchone()
        conn.close()
        assert row[0] == "pdf"
        assert "page 1" in row[1]

    def test_tenant_isolation(self, db):
        insert_rag(db, 1, "public", "T1 data")
        insert_rag(db, 2, "public", "T2 data")  # same name, different tenant

        conn = sqlite3.connect(db)
        rows = conn.execute(
            "SELECT tenant_id, data_content FROM rag_data WHERE data_name = 'public' ORDER BY tenant_id"
        ).fetchall()
        conn.close()
        assert len(rows) == 2
        assert rows[0] == (1, "T1 data")
        assert rows[1] == (2, "T2 data")

    def test_multiple_entries_per_tenant(self, db):
        insert_rag(db, 1, "doc1", "Content 1")
        insert_rag(db, 1, "doc2", "Content 2")
        insert_rag(db, 1, "doc3", "Content 3")

        conn = sqlite3.connect(db)
        count = conn.execute(
            "SELECT COUNT(*) FROM rag_data WHERE tenant_id = 1"
        ).fetchone()[0]
        conn.close()
        assert count == 3
