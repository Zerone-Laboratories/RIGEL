# filepath: /home/zerone/Projects/RIGEL_SERVICE/web_server.py
# This file is part of RIGEL Engine.
#
# Copyright (C) 2025 Zerone Laboratories
#
# RIGEL Engine is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# RIGEL Engine is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

from fastapi import FastAPI, HTTPException, File, UploadFile, Form, Depends, Header, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import numpy as np
import asyncio
import threading
import tempfile
import os
import concurrent.futures
import json
import uvicorn
import sqlite3
import hashlib
import time
import re
import secrets
import uuid
from pathlib import Path
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

from core.rigel import RigelOllama, RigelGroq, RigelUnifiedrouter, RigelDeepseek
from core.extensions.rigel_claude_code_integration import RigelClaude

_RIGEL_CLAUDE_ENABLED = os.getenv("RIGEL_CLAUDE_ENABLED", "false").lower() == "true"
from core.rdb import DBConn
from core.logger import SysLog
from helpers.vector_cache import VectorCache
from core.synth_n_recog import Synthesizer, Recognizer, LiveVoiceRecognizer
from core.vision import get_vision_engine
from langchain_mcp_adapters.client import MultiServerMCPClient
from dotenv import load_dotenv
from version import VERSION

# Initialize logging
syslog = SysLog(name="RigelWebServer", level="INFO", log_file="server.log")

# Load environment from .env (if present)
load_dotenv()

# Database initialization
DB_PATH = "rigel_usage.db"

# Admin key persistence
ADMIN_KEY_FILE = Path(__file__).resolve().parent / ".xadminkey"
ADMIN_API_KEY: Optional[str] = None


def _read_text_file(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None
    except Exception as e:
        syslog.warning("Failed reading %s: %s", str(path), str(e))
        return None


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", delete=False, dir=str(path.parent), encoding="utf-8") as tmp:
        tmp.write(text)
        tmp.write("\n")
        tmp_path = Path(tmp.name)

    os.chmod(tmp_path, 0o600)
    os.replace(str(tmp_path), str(path))


def load_or_create_admin_key() -> str:
    """Load admin key from env or .xadminkey; otherwise generate and persist."""
    env_key = (os.getenv("RIGEL_ADMIN_KEY") or "").strip()
    if env_key:
        return env_key

    file_key = _read_text_file(ADMIN_KEY_FILE)
    if file_key:
        return file_key

    generated = f"rigel_admin_{secrets.token_hex(16)}"
    try:
        _atomic_write_text(ADMIN_KEY_FILE, generated)
        syslog.info("Generated admin key and saved to %s", str(ADMIN_KEY_FILE))
    except Exception as e:
        syslog.warning(
            "Generated admin key but failed to persist to %s: %s",
            str(ADMIN_KEY_FILE),
            str(e),
        )
    return generated


def get_tools_sse_url() -> str:
    default_url = "http://localhost:8001/sse"
    raw_url = os.environ.get("RIGEL_MCP_TOOLS_SSE_URL", default_url)
    normalized_url = re.sub(r"\s+", "", raw_url)
    if normalized_url != raw_url:
        syslog.warning(
            "RIGEL_MCP_TOOLS_SSE_URL contained whitespace; normalized from '%s' to '%s'",
            raw_url,
            normalized_url,
        )
    return normalized_url or default_url

def init_database():
    """Initialize SQLite database for API key management and usage tracking"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create tenants table
    cursor.execute("""
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
    """)
    
    # Create usage table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER,
            endpoint TEXT NOT NULL,
            tokens_estimated INTEGER DEFAULT 0,
            duration_ms INTEGER DEFAULT 0,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (tenant_id) REFERENCES tenants (id)
        )
    """)
    
    # Create rate limiting table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rate_limits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER,
            endpoint TEXT NOT NULL,
            requests_count INTEGER DEFAULT 1,
            window_start TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (tenant_id) REFERENCES tenants (id),
            UNIQUE(tenant_id, endpoint, window_start)
        )
    """)
    
    conn.commit()
    conn.close()

def create_api_key(name: str, plan: str = "free") -> str:
    """Create a new API key for a tenant"""
    import secrets
    api_key = f"rigel_{secrets.token_urlsafe(32)}"
    api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    quotas = {
        "free": {"monthly": 1000, "daily": 100},
        "pro": {"monthly": 20000, "daily": 1000},
        "enterprise": {"monthly": 100000, "daily": 5000}
    }
    
    quota = quotas.get(plan, quotas["free"])
    
    cursor.execute("""
        INSERT INTO tenants (name, api_key_hash, plan, monthly_quota, daily_quota)
        VALUES (?, ?, ?, ?, ?)
    """, (name, api_key_hash, plan, quota["monthly"], quota["daily"]))
    
    conn.commit()
    conn.close()
    
    return api_key

def get_tenant_info(api_key: str) -> Optional[Dict[str, Any]]:
    """Get tenant information from API key"""
    if not api_key:
        return None
        
    api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, name, plan, active, monthly_quota, daily_quota
        FROM tenants 
        WHERE api_key_hash = ? AND active = 1
    """, (api_key_hash,))
    
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return None
        
    return {
        "tenant_id": row[0],
        "name": row[1],
        "plan": row[2],
        "active": row[3],
        "monthly_quota": row[4],
        "daily_quota": row[5]
    }

def check_rate_limit(tenant_id: int, endpoint: str, limit_override: Optional[int] = None) -> bool:
    """Check if tenant has exceeded rate limits"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get tenant info
    cursor.execute("SELECT plan FROM tenants WHERE id = ?", (tenant_id,))
    plan_row = cursor.fetchone()
    if not plan_row:
        conn.close()
        return False
    
    plan = plan_row[0]
    
    # Rate limits per plan (requests per minute)
    rate_limits = {
        "free": 10,
        "pro": 60,
        "enterprise": 300
    }
    
    limit = limit_override if limit_override is not None else rate_limits.get(plan, 10)
    
    # Check current minute
    current_time = datetime.now()
    window_start = current_time.replace(second=0, microsecond=0)
    
    cursor.execute("""
        SELECT requests_count FROM rate_limits 
        WHERE tenant_id = ? AND endpoint = ? AND window_start = ?
    """, (tenant_id, endpoint, window_start))
    
    row = cursor.fetchone()
    
    if row:
        if row[0] >= limit:
            conn.close()
            return False
        # Update count
        cursor.execute("""
            UPDATE rate_limits 
            SET requests_count = requests_count + 1
            WHERE tenant_id = ? AND endpoint = ? AND window_start = ?
        """, (tenant_id, endpoint, window_start))
    else:
        # Insert new record
        cursor.execute("""
            INSERT INTO rate_limits (tenant_id, endpoint, requests_count, window_start)
            VALUES (?, ?, 1, ?)
        """, (tenant_id, endpoint, window_start))
    
    conn.commit()
    conn.close()
    return True

def check_usage_quota(tenant_id: int) -> Dict[str, Any]:
    """Check tenant's usage against their quotas"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get tenant quotas
    cursor.execute("""
        SELECT monthly_quota, daily_quota FROM tenants WHERE id = ?
    """, (tenant_id,))
    
    quota_row = cursor.fetchone()
    if not quota_row:
        conn.close()
        return {"allowed": False, "reason": "Invalid tenant"}
    
    monthly_quota, daily_quota = quota_row
    
    # Check monthly usage
    cursor.execute("""
        SELECT COUNT(*) FROM usage 
        WHERE tenant_id = ? AND timestamp >= date('now', '-30 days')
    """, (tenant_id,))
    monthly_usage = cursor.fetchone()[0]
    
    # Check daily usage
    cursor.execute("""
        SELECT COUNT(*) FROM usage 
        WHERE tenant_id = ? AND date(timestamp) = date('now')
    """, (tenant_id,))
    daily_usage = cursor.fetchone()[0]
    
    conn.close()
    
    if monthly_usage >= monthly_quota:
        return {
            "allowed": False, 
            "reason": f"Monthly quota exceeded ({monthly_usage}/{monthly_quota})"
        }
    
    if daily_usage >= daily_quota:
        return {
            "allowed": False, 
            "reason": f"Daily quota exceeded ({daily_usage}/{daily_quota})"
        }
    
    return {
        "allowed": True,
        "monthly_usage": monthly_usage,
        "monthly_quota": monthly_quota,
        "daily_usage": daily_usage,
        "daily_quota": daily_quota
    }

def record_usage(tenant_id: int, endpoint: str, tokens: int = 0, duration_ms: int = 0):
    """Record API usage for billing and analytics"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO usage (tenant_id, endpoint, tokens_estimated, duration_ms)
        VALUES (?, ?, ?, ?)
    """, (tenant_id, endpoint, tokens, duration_ms))
    
    conn.commit()
    conn.close()

# API Key dependency
async def require_api_key(x_api_key: str = Header(None, alias="X-API-Key")) -> Dict[str, Any]:
    """FastAPI dependency to require and validate API key"""
    if not x_api_key:
        raise HTTPException(
            status_code=401, 
            detail="Missing API key. Please provide X-API-Key header."
        )
    
    tenant_info = get_tenant_info(x_api_key)
    if not tenant_info:
        raise HTTPException(
            status_code=403, 
            detail="Invalid or inactive API key."
        )
    
    return tenant_info

def _is_localhost_client(client_host: Optional[str]) -> bool:
    if not client_host:
        return False
    return (
        client_host in {"127.0.0.1", "::1", "localhost"}
        or client_host.startswith("127.")
        or client_host.startswith("::ffff:127.")
    )


async def check_quotas_and_limits(
    tenant_info: Dict[str, Any],
    endpoint: str,
    client_host: Optional[str] = None,
) -> Dict[str, Any]:
    """Check rate limits and usage quotas"""
    tenant_id = tenant_info["tenant_id"]
    
    local_client = _is_localhost_client(client_host)
    disable_local_limit = os.getenv("RIGEL_DISABLE_LOCALHOST_RATE_LIMIT", "false").lower() == "true"
    localhost_limit_env = os.getenv("RIGEL_LOCALHOST_RATE_LIMIT_PER_MIN", "").strip()
    localhost_limit_override: Optional[int] = None
    if local_client and localhost_limit_env.isdigit():
        localhost_limit_override = int(localhost_limit_env)

    # Check rate limiting
    if not (local_client and disable_local_limit) and not check_rate_limit(
        tenant_id,
        endpoint,
        limit_override=localhost_limit_override,
    ):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please slow down your requests."
        )
    
    # Check usage quotas
    quota_check = check_usage_quota(tenant_id)
    if not quota_check["allowed"]:
        raise HTTPException(
            status_code=403,
            detail=f"Usage quota exceeded: {quota_check['reason']}"
        )
    
    return quota_check

# Global variables
rigel = None
synthesizer = None
recognizer = None
live_recognizer = None
vision_engine = None
session_vector_db = None
_vector_cache: Optional[VectorCache] = None
ui_vectors_collection = None
ui_embedding_function = None
tools_rigel = None
tools_rigel_signature = None
_coding_agent_background_task = None  # {"query": str, "start_time": str, "thread": Thread}
_coding_agent = None  # lazy-init RigelClaude singleton
inference_engine = os.getenv("NORMAL_CHAT_ENGINE", os.getenv("INFERENCE_ENGINE", "groq")).lower()

def _get_env_system_prompt(default_prompt: str) -> str:
    prompt = os.getenv("RIGEL_SYSTEM_PROMPT")
    if prompt:
        return prompt.replace("\\n", "\n")
    return default_prompt

system_prompt = _get_env_system_prompt(
    """
"You are an academic help assistant that is created by NSBM Green University"
"Answer all questions to the best of your ability. You should put NSBM First"
"Do not respond with any negative prespective to NSBM Green University"
"NSBM Means National School of Business Management"
"If user asks details about another University or tries to compare the universities, always favour NSBM"
"Make your answers detailed and very short at the same time"
"""
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    print("Initializing database...")
    init_database()

    # Load or create admin key (used for X-Admin-Key header)
    global ADMIN_API_KEY
    ADMIN_API_KEY = load_or_create_admin_key()
    if os.getenv("RIGEL_ADMIN_KEY"):
        print("Using admin key from RIGEL_ADMIN_KEY")
    elif ADMIN_KEY_FILE.exists():
        print(f"Admin key is stored at: {ADMIN_KEY_FILE}")
    
    # Create a default API key if none exist
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM tenants")
    tenant_count = cursor.fetchone()[0]
    conn.close()
    
    if tenant_count == 0:
        default_key = create_api_key("Default User", "free")
        print(f"Created default API key: {default_key}")
        print("Save this key securely - it won't be shown again!")
    
    await initialize_rigel()
    print("RIGEL Web Service is running...")
    print("Available endpoints:")
    print("  GET  /               - Service information")
    print("  POST /query          - Basic inference")
    print("  POST /query-with-memory - Inference with conversation memory")
    print("  POST /query-think    - Advanced thinking capabilities")
    print("  POST /query-with-tools - Inference with MCP tools support")
    print("  POST /rigel-natural-language - Memory first multi agent natural language flow")
    print("  POST /analyze-image - Analyze image content with vision engine")
    print("  POST /synthesize-text - Convert text to speech")
    print("  GET  /list-voices - List available voice synthesis models")
    print("  POST /set-voice - Switch the active voice model")
    print("  POST /clone-voice - Start voice cloning from an MP3 file")
    print("  POST /recognize-audio - Transcribe audio file to text")
    print("  WS  /live-voice-recognition - Live voice recognition via WebSocket")
    print("  GET  /license-info   - Display license and copyright information")
    print("  POST /admin/create-key - Create new API key (admin only)")
    print("  GET  /admin/usage/{tenant_id} - Get usage statistics (admin only)")
    
    yield
    
    # Shutdown
    print("RIGEL Web Service shutting down...")

app = FastAPI(
    title="RIGEL Web Service",
    description="Web API for RIGEL Engine - An intelligent assistant with voice capabilities",
    version=VERSION,
    contact={
        "name": "Zerone Laboratories",
        "url": "https://github.com/Zerone-Laboratories/RIGEL",
    },
    license_info={
        "name": "GNU Affero General Public License v3.0",
        "url": "https://www.gnu.org/licenses/agpl-3.0.html",
    },
    lifespan=lifespan
)

# Simple static UI for manual API testing
_ui_dir = Path(__file__).resolve().parent / "assets" / "web_ui"
if _ui_dir.exists():
    app.mount("/ui", StaticFiles(directory=str(_ui_dir), html=True), name="ui")

# Request/Response Models
class QueryRequest(BaseModel):
    query: str
    system_prompt: Optional[str] = None

class QueryWithMemoryRequest(BaseModel):
    query: str
    id: str

class NaturalLanguageRequest(BaseModel):
    query: str
    id: Optional[str] = "default"
    voice_recognition_confidence: Optional[float] = None

class AnalyzeImageRequest(BaseModel):
    image_path: str
    prompt: str

class AnalyzeImageResponse(BaseModel):
    result: Dict[str, Any]

class SynthesizeRequest(BaseModel):
    text: str
    mode: Optional[str] = "chunk"
    voice: Optional[str] = None

class SetVoiceRequest(BaseModel):
    voice: str

class CloneVoiceRequest(BaseModel):
    mp3_path: str
    voice_name: str
    language: Optional[str] = "English (U.S.)"

class RecognizeRequest(BaseModel):
    model: Optional[str] = "tiny"

class QueryResponse(BaseModel):
    response: str

class SynthesizeResponse(BaseModel):
    result: str

class RecognizeResponse(BaseModel):
    transcription: str

class LicenseResponse(BaseModel):
    license_info: str

class CreateKeyRequest(BaseModel):
    name: str
    plan: Optional[str] = "free"

class CreateKeyResponse(BaseModel):
    api_key: str
    tenant_id: int
    plan: str

class UsageStatsResponse(BaseModel):
    tenant_id: int
    name: str
    plan: str
    monthly_usage: int
    monthly_quota: int
    daily_usage: int
    daily_quota: int
    total_requests: int

class InferenceEngineRequest(BaseModel):
    engine: str  # "groq" or "ollama"

class InferenceEngineResponse(BaseModel):
    engine: str
    status: str

class VectorAddRequest(BaseModel):
    id: str
    vector: List[float]
    document: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    collection: Optional[str] = "ui_vectors"

class VectorSearchRequest(BaseModel):
    vector: List[float]
    top_k: Optional[int] = 5
    collection: Optional[str] = "ui_vectors"

class VectorTextSearchRequest(BaseModel):
    text: str
    top_k: Optional[int] = 5
    collection: Optional[str] = "ui_vectors"

class VectorCosineRequest(BaseModel):
    id_a: Optional[str] = None
    id_b: Optional[str] = None
    vector_a: Optional[List[float]] = None
    vector_b: Optional[List[float]] = None
    collection: Optional[str] = "ui_vectors"

class RecordCreateRequest(BaseModel):
    id: Optional[str] = None
    text: str
    metadata: Optional[Dict[str, Any]] = None
    vector: Optional[List[float]] = None
    collection: Optional[str] = "ui_vectors"

class RecordUpdateRequest(BaseModel):
    text: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    vector: Optional[List[float]] = None
    collection: Optional[str] = "ui_vectors"

class RecordSearchRequest(BaseModel):
    text: str
    top_k: Optional[int] = 10
    collection: Optional[str] = "ui_vectors"

# ---------------------------------------------------------------------------
# CodingAgent (RigelClaude) request/response models
# ---------------------------------------------------------------------------

class CodingGenerateRequest(BaseModel):
    specification: str
    language: str = "python"

class CodingReviewRequest(BaseModel):
    code: str
    language: str = "python"

class CodingDebugRequest(BaseModel):
    code: str
    error: str
    language: str = "python"

class CodingRefactorRequest(BaseModel):
    code: str
    instructions: str
    language: str = "python"

class CodingExplainRequest(BaseModel):
    code: str
    language: str = "python"

class CodingExecuteRequest(BaseModel):
    file_path: str
    args: Optional[List[str]] = None

class CodingHistoryRequest(BaseModel):
    last_n: int = 20


def _sanitize_natural_language_output(text: str) -> str:
    """Sanitize output to plain natural language without markdown-like formatting."""
    if not text:
        return ""

    cleaned = re.sub(r"<\s*think\s*>.*?<\s*/\s*think\s*>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"\bthink\b.*?\s/think\b", " ", cleaned, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"^\s*CALL[\s_\-]*TOOL[\s_\-]*AGENT\s*:\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.replace("\n", " ")
    cleaned = re.sub(r"[*_`~#<>\[\]{}|\\]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned

def _normalize_home_paths(text: str) -> str:
    """Normalize ~ paths to an absolute host home path for downstream execution."""
    if not text:
        return text
    preferred_home = os.getenv("HOST_HOME", "/home/zerone").rstrip("/")
    return re.sub(r"(?<![A-Za-z0-9_])~(?=/|$)", preferred_home, text)

def _extract_tool_agent_task(decision_text: str) -> Optional[str]:
    if not decision_text:
        return None

    match = re.match(r"^\s*CALL[\s_\-]*TOOL[\s_\-]*AGENT\s*:\s*(.*)$", decision_text, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    return _normalize_home_paths(match.group(1).strip())

def _resolve_tool_task(decision_text: str, user_query: str, thread_id: str) -> Optional[str]:
    tool_task = _extract_tool_agent_task(decision_text)
    if tool_task is not None:
        return tool_task or user_query

    if _should_delegate_to_tool_agent(user_query, decision_text, thread_id):
        return user_query

    return None

def _should_delegate_to_tool_agent(user_query: str, memory_decision_text: str, thread_id: str) -> bool:
    global rigel

    if rigel is None:
        return False

    router_prompt = """
    You are a strict routing classifier.
    Decide if the user request requires external tool execution.
    Reply with exactly one word only: YES or NO.
    YES if command execution, system state checks, files, apps, processes, current time/date, network, environment inspection, or other real-world retrieval/actions are needed.
    NO if the request can be answered directly from conversation context only.
    """

    router_thread_id = f"{thread_id}_tool_router"
    router_input = (
        f"User request: {user_query}\n"
        f"Memory decision draft: {memory_decision_text}\n"
        "Return YES or NO only."
    )

    try:
        router_response = rigel.inference_with_memory(
            messages=[
                ("system", router_prompt),
                ("human", router_input)
            ],
            thread_id=router_thread_id,
            RAG=False
        )
        response_text = router_response.content if hasattr(router_response, "content") else str(router_response)
        return response_text.strip().upper().startswith("YES")
    except Exception:
        return False

def _looks_like_capability_refusal(text: str) -> bool:
    if not text:
        return False

    refusal_patterns = [
        r"\bi\s+don'?t\s+have\s+access\b",
        r"\bi\s+cannot\s+access\b",
        r"\bi\s+can'?t\s+access\b",
        r"\bno\s+real\s*[- ]?time\s+data\b",
        r"\bi\s+am\s+unable\s+to\b",
    ]
    for pattern in refusal_patterns:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return True
    return False

def _get_session_vector_db() -> Optional[DBConn]:
    global session_vector_db
    if session_vector_db is None:
        try:
            session_vector_db = DBConn()
        except Exception as e:
            syslog.warning(f"Vector DB unavailable: {str(e)}")
            session_vector_db = False
    return session_vector_db if session_vector_db is not False else None

def _get_vector_cache() -> VectorCache:
    """Lazy singleton for the NL vector cache."""
    global _vector_cache
    if _vector_cache is None:
        _vector_cache = VectorCache()
    return _vector_cache

def _get_vector_session_context(session_id: str, query: str) -> str:
    db = _get_session_vector_db()
    if db is None:
        return ""
    try:
        return db.search_session_context(session_id=session_id, query=query, n_results=4)
    except Exception as e:
        syslog.warning(f"Failed to retrieve vector session context: {str(e)}")
        return ""

def _save_vector_session_turn(session_id: str, user_text: str, assistant_text: str):
    db = _get_session_vector_db()
    if db is None:
        return
    try:
        db.save_session_turn(
            session_id=session_id,
            user_text=user_text,
            assistant_text=assistant_text,
            source="web-rigel-natural-language",
        )
    except Exception as e:
        syslog.warning(f"Failed to save vector session turn: {str(e)}")

def _sanitize_collection_name(collection: Optional[str]) -> str:
    name = (collection or "ui_vectors").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Collection name cannot be empty")
    if not re.match(r"^[A-Za-z0-9._-]{1,128}$", name):
        raise HTTPException(status_code=400, detail="Invalid collection name")
    return name

def _get_ui_embedding_function():
    global ui_embedding_function
    if ui_embedding_function is None:
        ui_embedding_function = DefaultEmbeddingFunction()
    return ui_embedding_function

def _embed_text(text: str) -> List[float]:
    clean = (text or "").strip()
    if not clean:
        raise HTTPException(status_code=400, detail="text is required")
    try:
        return _get_ui_embedding_function()([clean])[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to embed text: {str(e)}")

def _get_ui_vectors_collection(collection_name: str = "ui_vectors"):
    global ui_vectors_collection
    db = _get_session_vector_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Vector database is unavailable")

    collection_name = _sanitize_collection_name(collection_name)
    cache = ui_vectors_collection if isinstance(ui_vectors_collection, dict) else {}
    if collection_name in cache:
        return cache[collection_name]

    try:
        collection = db.chroma_client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
    except Exception:
        collection = db.chroma_client.get_or_create_collection(name=collection_name)

    cache[collection_name] = collection
    ui_vectors_collection = cache
    return collection

def _get_ui_vectors_collection_for_text(collection_name: str = "ui_vectors"):
    db = _get_session_vector_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Vector database is unavailable")
    name = _sanitize_collection_name(collection_name)
    return db.chroma_client.get_collection(
        name=name,
        embedding_function=_get_ui_embedding_function(),
    )

def _normalize_vector(vector: List[float], field_name: str = "vector") -> List[float]:
    if not isinstance(vector, list) or not vector:
        raise HTTPException(status_code=400, detail=f"{field_name} must be a non-empty array of numbers")
    try:
        parsed = [float(v) for v in vector]
    except Exception:
        raise HTTPException(status_code=400, detail=f"{field_name} must contain only numeric values")
    return parsed

def _cosine_similarity(vector_a: List[float], vector_b: List[float]) -> float:
    a = np.array(vector_a, dtype=np.float32)
    b = np.array(vector_b, dtype=np.float32)
    if a.shape != b.shape:
        raise HTTPException(status_code=400, detail="Vectors must have the same dimensionality")

    norm_a = float(np.linalg.norm(a))
    norm_b = float(np.linalg.norm(b))
    if norm_a == 0.0 or norm_b == 0.0:
        raise HTTPException(status_code=400, detail="Zero vectors are not valid for cosine similarity")

    return float(np.dot(a, b) / (norm_a * norm_b))

# Routes
@app.get("/", response_model=dict)
async def root():
    """Root endpoint with service information - no auth required"""
    global inference_engine
    
    return {
        "service": "RIGEL Web Service",
        "version": VERSION,
        "copyright": "Copyright (C) 2025 Zerone Laboratories",
        "license": "GNU Affero General Public License v3.0",
        "current_inference_engine": inference_engine,
        "authentication": "API key required for all endpoints except root and license-info",
        "endpoints": [
            "/query",
            "/query-with-memory", 
            "/query-think",
            "/query-with-tools",
            "/rigel-natural-language",
            "/analyze-image",
            "/synthesize-text",
            "/recognize-audio",
            "/license-info",
            "/admin/create-key",
            "/admin/usage/{tenant_id}",
            "/admin/list-tenants",
            "/admin/switch-inference-engine",
            "/admin/current-inference-engine"
        ]
    }

@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest, tenant_info: Dict[str, Any] = Depends(require_api_key)):
    """Basic inference endpoint"""
    global system_prompt, rigel
    
    # Check quotas and rate limits
    await check_quotas_and_limits(tenant_info, "query")
    
    if rigel is None:
        raise HTTPException(status_code=500, detail="RIGEL backend not initialized")
    
    start_time = time.time()
    
    try:
        # Use provided system prompt or default to global system prompt
        current_system_prompt = request.system_prompt if request.system_prompt else system_prompt
        
        messages = [
            ("system", f"{current_system_prompt}"),
            ("human", f"{request.query}")
        ]
        response = rigel.inference(messages=messages)
        
        # Record usage
        duration_ms = int((time.time() - start_time) * 1000)
        tokens_estimated = len(request.query.split()) + len(response.content.split())
        record_usage(tenant_info["tenant_id"], "query", tokens_estimated, duration_ms)
        
        return QueryResponse(response=response.content)
    except Exception as e:
        syslog.error(f"Error in query: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")

@app.post("/query-with-memory", response_model=QueryResponse)
async def query_with_memory(request: QueryWithMemoryRequest, tenant_info: Dict[str, Any] = Depends(require_api_key)):
    """Inference with conversation memory"""
    global system_prompt, rigel
    
    # Check quotas and rate limits
    await check_quotas_and_limits(tenant_info, "query-with-memory")
    
    if rigel is None:
        raise HTTPException(status_code=500, detail="RIGEL backend not initialized")
    
    start_time = time.time()
    
    try:
        messages = [
            (
                "system",
                system_prompt
            ),
            (
                "human", f"{request.query}"
            )
        ]
        
        response = rigel.inference_with_memory(messages=messages, thread_id=request.id)
        syslog.info(response)
        # Record usage
        duration_ms = int((time.time() - start_time) * 1000)
        tokens_estimated = len(request.query.split()) + len(response.content.split())
        record_usage(tenant_info["tenant_id"], "query-with-memory", tokens_estimated, duration_ms)
        
        return QueryResponse(response=response.content)
    except Exception as e:
        syslog.error(f"Error in query with memory: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing query with memory: {str(e)}")

@app.post("/query-think", response_model=QueryResponse)
async def query_think(request: QueryRequest, tenant_info: Dict[str, Any] = Depends(require_api_key)):
    """Advanced thinking capabilities"""
    global rigel, system_prompt
    
    # Check quotas and rate limits
    await check_quotas_and_limits(tenant_info, "query-think")
    
    if rigel is None:
        raise HTTPException(status_code=500, detail="RIGEL backend not initialized")
    
    start_time = time.time()
    
    try:
        # For query_think, we need to modify the think method to accept a system prompt
        # Since the core implementation doesn't directly support this,
        # we'll have to modify the prompt with our system prompt
        
        # Store the original thought_prompt
        original_thought_prompt = rigel.thought_prompt
        
        # Use provided system prompt or default to global system prompt
        current_system_prompt = request.system_prompt if request.system_prompt else system_prompt
        
        # Temporarily modify the thought_prompt to include the system prompt
        modified_thought_prompt = f"""
        {current_system_prompt}
        
        Think of the best way to do this and list it out in a short manner. nothing more or nothing less.
        If the thinking process is done, say exactly 'The task is done'. If it's impossible exactly say 'The task is impossible'.
        """
        
        # Set the modified thought prompt
        rigel.thought_prompt = modified_thought_prompt
        
        # Call the think method
        response = rigel.think(request.query)
        
        # Restore original thought prompt
        rigel.thought_prompt = original_thought_prompt
        
        # Record usage (thinking uses more resources, count as 2x tokens)
        duration_ms = int((time.time() - start_time) * 1000)
        tokens_estimated = (len(request.query.split()) + len(response.split())) * 2
        record_usage(tenant_info["tenant_id"], "query-think", tokens_estimated, duration_ms)
        
        return QueryResponse(response=response)
    except Exception as e:
        syslog.error(f"Error in query think: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing think query: {str(e)}")

@app.post("/query-with-tools", response_model=QueryResponse)
async def query_with_tools(request: QueryRequest, tenant_info: Dict[str, Any] = Depends(require_api_key)):
    """Inference with MCP tools support"""
    global rigel, system_prompt
    
    # Check quotas and rate limits
    await check_quotas_and_limits(tenant_info, "query-with-tools")
    
    if rigel is None:
        raise HTTPException(status_code=500, detail="RIGEL backend not initialized")
    
    syslog.info(f"QueryWithTools called with query: {request.query[:100]}... by tenant {tenant_info['tenant_id']}")

    start_time = time.time()
    tool_rigel = _get_or_create_tool_rigel()
    if tool_rigel is None:
        raise HTTPException(status_code=500, detail="Tool agent is not initialized")

    original_continuity = tool_rigel.continuity

    try:
        current_system_prompt = request.system_prompt if request.system_prompt else system_prompt
        tool_rigel.continuity = f"""
        {current_system_prompt}

        {original_continuity}
        """

        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(_run_async_tools_query, request.query)
            result = future.result(timeout=120)

        response_content = result.content if hasattr(result, "content") else str(result)

        duration_ms = int((time.time() - start_time) * 1000)
        tokens_estimated = (len(request.query.split()) + len(response_content.split())) * 3
        record_usage(tenant_info["tenant_id"], "query-with-tools", tokens_estimated, duration_ms)

        return QueryResponse(response=response_content)

    except concurrent.futures.TimeoutError:
        error_msg = "Query with tools timed out after 2 minutes"
        syslog.error(error_msg)
        raise HTTPException(status_code=408, detail=error_msg)
    except Exception as e:
        error_msg = f"Error occurred during tool-based inference: {str(e)}"
        syslog.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)
    finally:
        tool_rigel.continuity = original_continuity

def _run_async_tools_query(query):
    """Helper function to run async tools query"""
    tool_rigel = _get_or_create_tool_rigel()
    if tool_rigel is None:
        raise RuntimeError("Tool agent is not initialized")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(tool_rigel.inference_with_tools(query))
    finally:
        loop.close()

def _execute_nl_tool_task(tool_task: str, thread_id: str):
    return _run_async_tools_query(tool_task)

# --- Coding agent helpers (RigelClaude) ---

def _has_call_coding_agent(text: str) -> bool:
    """Check if text contains a [CALL_CODING_AGENT: ...] pattern."""
    return _extract_coding_agent_task(text or "") is not None

def _has_coding_agent_status_check(text: str) -> bool:
    """Check if text contains [CODING_AGENT_STATUS_CHECK]."""
    pattern = r'\[CODING[\s_\-]*AGENT[\s_\-]*STATUS[\s_\-]*CHECK\]'
    return bool(re.search(pattern, text, flags=re.IGNORECASE))

def _extract_coding_agent_task(decision_text: str) -> Optional[str]:
    """Extract task from [CALL_CODING_AGENT: <task>] and tolerate missing closing bracket."""
    if not decision_text:
        return None
    patterns = [
        r"\[CALL[\s_\-]*CODING[\s_\-]*AGENT\s*:\s*(.*?)(?:\]|$)",
        r"CALL[\s_\-]*CODING[\s_\-]*AGENT\s*:\s*(.*?)(?:\]|$)",
    ]
    for pattern in patterns:
        match = re.search(pattern, decision_text, flags=re.IGNORECASE | re.DOTALL)
        if match:
            task = match.group(1).strip()
            return _normalize_home_paths(task) if task else None
    return None

def _get_or_create_coding_agent():
    """Return the lazy-init RigelClaude singleton, or None if disabled."""
    global _coding_agent
    if not _RIGEL_CLAUDE_ENABLED:
        return None
    if _coding_agent is None:
        syslog.info("Creating RigelClaude coding agent (lazy init)")
        _coding_agent = RigelClaude(auto_launch=False)
    return _coding_agent

def _get_coding_agent_status_text() -> str:
    """Return a natural-language summary of the coding agent's status."""
    global _coding_agent_background_task

    agent = _get_or_create_coding_agent()
    if agent is None:
        return "Coding agent is not available (RigelClaude is disabled)."

    status = agent.get_status()

    if _coding_agent_background_task is not None:
        task_query = _coding_agent_background_task.get("query", "unknown")
        start_time = _coding_agent_background_task.get("start_time", "unknown")
        error = _coding_agent_background_task.get("error")
        end_time = _coding_agent_background_task.get("end_time", "unknown")
        if _coding_agent_background_task["thread"].is_alive():
            return (
                f"Coding agent is currently working on: '{task_query}'. "
                f"Started at: {start_time}. "
                f"Status: {status.get('status', 'unknown')}. "
                f"Log entries so far: {status.get('log_entries', 0)}."
            )
        if error:
            return (
                f"Coding agent task failed: '{task_query}'. "
                f"Started at: {start_time}. Ended at: {end_time}. "
                f"Status: {status.get('status', 'unknown')}. Error: {error}"
            )
        else:
            return f"Coding agent has finished the task: '{task_query}'. Status: {status.get('status', 'unknown')}."

    return f"Coding agent is idle. Status: {status.get('status', 'unknown')}."

def _spawn_background_coding_task(task: str):
    """Launch a coding task in a background thread."""
    global _coding_agent_background_task

    agent = _get_or_create_coding_agent()
    if agent is None:
        return

    task_record = {
        "query": task,
        "start_time": datetime.now().isoformat(),
        "end_time": None,
        "result_preview": None,
        "error": None,
        "thread": None,
    }
    _coding_agent_background_task = task_record

    def _run_coding():
        try:
            result = agent.coding_task(task)
            task_record["result_preview"] = (result or "")[:300]
        except Exception as e:
            task_record["error"] = str(e)
            syslog.error(f"Background coding task error: {e}")
        finally:
            task_record["end_time"] = datetime.now().isoformat()

    thread = threading.Thread(target=_run_coding, daemon=True)
    task_record["thread"] = thread
    thread.start()
    syslog.info(f"Coding agent started background task: {task[:100]}...")


def _get_or_create_tool_rigel():
    global tools_rigel, tools_rigel_signature

    tool_engine = os.getenv("TOOL_CALL_ENGINE", "ollama").lower()
    if tool_engine == "ollama":
        default_tool_model = "qwen3:0.6b"
    elif tool_engine == "deepseek":
        default_tool_model = os.getenv("TOOL_CALL_DEEPSEEK_MODEL", os.getenv("DEEPSEEK_MODEL", "deepseek-v3"))
    else:
        default_tool_model = os.getenv("TOOL_CALL_GROQ_MODEL", "qwen/qwen3-32b")
    tool_model = os.getenv("TOOL_CALL_MODEL", default_tool_model)
    tool_temp = float(os.getenv("TOOL_TEMPERATURE", os.getenv("TEMPERATURE", "0.0")))
    tools_sse_url = get_tools_sse_url()

    current_signature = (tool_engine, tool_model, tool_temp, tools_sse_url)
    if tools_rigel is not None and tools_rigel_signature == current_signature:
        return tools_rigel

    tool_mcp = MultiServerMCPClient(
        {
            "rigel tools": {
                "url": tools_sse_url,
                "transport": "sse",
            }
        },
    )

    if tool_engine == "groq":
        tools_rigel = RigelGroq(model_name=tool_model, temp=tool_temp, mcp_endpoint=tool_mcp)
    elif tool_engine == "deepseek":
        tools_rigel = RigelDeepseek(model_name=tool_model, temp=tool_temp, mcp_endpoint=tool_mcp)
    else:
        tools_rigel = RigelOllama(model_name=tool_model, mcp_endpoint=tool_mcp)
    tools_rigel_signature = current_signature
    return tools_rigel

@app.post("/rigel-natural-language", response_model=QueryResponse)
async def rigel_natural_language(request: NaturalLanguageRequest, tenant_info: Dict[str, Any] = Depends(require_api_key)):
    """Memory-first multi-agent endpoint with tool, coding agent delegation and natural language-only output."""
    global rigel, system_prompt, _coding_agent_background_task

    await check_quotas_and_limits(tenant_info, "rigel-natural-language")

    if rigel is None:
        raise HTTPException(status_code=500, detail="RIGEL backend not initialized")

    start_time = time.time()
    thread_id = request.id or "default"
    confidence = request.voice_recognition_confidence
    if confidence is not None and confidence < 0.5:
        return QueryResponse(
            response="Voice Recognition Confidence too low, Please rephrase the query"
        )

    try:
        current_system_prompt = system_prompt
        session_context = _get_vector_session_context(thread_id, request.query)
        user_input_with_context = (
            f"User request: {request.query}\nSession context: {session_context}"
            if session_context else f"User request: {request.query}"
        )

        memory_agent_prompt = f"""
        {current_system_prompt}

        You are the memory / decision agent. You do not have tool capabilities yourself.
        Decide what kind of execution the user request needs, if any.

        --- TOOL AGENT ---
        If the request needs command execution, system state checks, file operations,
        app/process management, time/date, network inspection, or web browsing,
        reply exactly:
        CALL_TOOL_AGENT: <single concise task for the tool agent>

        --- CODING AGENT ---
        If the request involves writing code, generating a project, debugging,
        refactoring, code review, creating files/scripts, building software,
        or any software engineering task, reply exactly:
        [CALL_CODING_AGENT: <detailed task for the coding agent>]
        The coding agent runs in the BACKGROUND. When you activate it, immediately
        inform the user that the coding agent has started and they can check status.

        --- STATUS CHECK ---
        If the user asks about the coding agent's progress or status, reply:
        [CODING_AGENT_STATUS_CHECK]
        You will receive the status and report it to the user.

        If no tools or agents are needed, answer directly.

        Style rules for your final user-facing message:
        Use only natural language.
        Keep it short and concise whenever possible.
        No lists.
        No tutorials.
        No markdown.
        """

        # --- VECTOR CACHE: memory_agent ---
        _vc = _get_vector_cache()
        _cached_decision = _vc.lookup(request.query, tag="memory_agent")
        if _cached_decision:
            syslog.info("[VectorCache] tripped")
            syslog.info("[VECTOR CACHE HIT] memory_agent — skipping memory agent LLM")
            decision_text = _cached_decision
        else:
            memory_decision = rigel.inference_with_memory(
                messages=[
                    ("system", memory_agent_prompt),
                    ("human", user_input_with_context)
                ],
                thread_id=thread_id,
                RAG=False
            )
            decision_text = memory_decision.content if hasattr(memory_decision, "content") else str(memory_decision)
            decision_text = decision_text.strip()
            # Submit to the background classifier queue — non-blocking.
            # The worker thread will classify the query and only write to
            # VectorCache if it is standalone (context-independent).
            from helpers.standalone_classifier import get_cache_writer_queue  # noqa: PLC0415
            get_cache_writer_queue().submit(request.query, decision_text, tag="memory_agent")

        delegated = False
        tool_task = _resolve_tool_task(decision_text, request.query, thread_id)

        response_content = decision_text
        max_tool_rounds = int(os.getenv("NATURAL_LANGUAGE_MAX_TOOL_ROUNDS", "3"))
        round_count = 0

        # --- CODING AGENT STATUS CHECK (before tool loop) ---
        if _has_coding_agent_status_check(decision_text):
            syslog.info("CODING_AGENT_STATUS_CHECK detected")
            status_text = _get_coding_agent_status_text()
            status_summary = rigel.inference_with_memory(
                messages=[
                    ("system", f"{current_system_prompt}\n\nYou are the memory agent."),
                    ("human", f"Coding agent status: {status_text}\n\nReport this to the user in natural language."),
                ],
                thread_id=thread_id,
                RAG=False
            )
            response_content = status_summary.content if hasattr(status_summary, "content") else str(status_summary)
            response_content = _sanitize_natural_language_output(response_content)
            _save_vector_session_turn(thread_id, request.query, response_content)
            return QueryResponse(response=response_content)

        # --- CODING AGENT (fires background task, returns immediately) ---
        elif _has_call_coding_agent(decision_text):
            syslog.info("CALL_CODING_AGENT detected, spawning background task")
            coding_task = _extract_coding_agent_task(decision_text)
            if coding_task:
                _spawn_background_coding_task(coding_task)
            notification_prompt = f"""
            {current_system_prompt}

            You are the memory agent.
            The coding agent has been started in the background with this task:
            '{coding_task or request.query}'

            Inform the user that the coding agent is now working in the background.
            Tell them they can check its status by asking "how is the coding agent doing?"
            or "check coding agent status".
            Keep it short and natural.
            """
            final_response = rigel.inference_with_memory(
                messages=[
                    ("system", notification_prompt),
                    ("human", f"User request: {request.query}")
                ],
                thread_id=thread_id,
                RAG=False
            )
            response_content = final_response.content if hasattr(final_response, "content") else str(final_response)
            response_content = _sanitize_natural_language_output(response_content)
            _save_vector_session_turn(thread_id, request.query, response_content)
            return QueryResponse(response=response_content)

        # --- TOOL AGENT LOOP ---
        while tool_task is not None and round_count < max_tool_rounds:
            delegated = True
            round_count += 1
            tool_task = tool_task or request.query

            with concurrent.futures.ThreadPoolExecutor() as executor:
                tool_future = executor.submit(_execute_nl_tool_task, tool_task, thread_id)
                tool_result = tool_future.result(timeout=120)

            tool_output_text = tool_result.content if hasattr(tool_result, "content") else str(tool_result)

            post_tool_prompt = f"""
            {current_system_prompt}

            You are the memory agent.
            You do not have tool capabilities.
            You now received tool output.

            If another tool call is still required, reply exactly:
            CALL_TOOL_AGENT: <single concise follow-up task>

            If no further tool call is needed, provide the final response naturally.

            Style rules:
            Use only natural language.
            Keep it short and concise whenever possible.
            No lists.
            No tutorials.
            No markdown.
            """

            post_tool_decision = rigel.inference_with_memory(
                messages=[
                    ("system", post_tool_prompt),
                    (
                        "human",
                        f"User request: {request.query}\nSession context: {session_context}\nTool output round {round_count}: {tool_output_text}"
                    )
                ],
                thread_id=thread_id,
                RAG=False
            )
            response_content = post_tool_decision.content if hasattr(post_tool_decision, "content") else str(post_tool_decision)
            response_content = response_content.strip()
            tool_task = _resolve_tool_task(response_content, request.query, thread_id)

        # If tool stage decides to delegate coding agent/status, handle it now.
        if _has_coding_agent_status_check(response_content):
            status_text = _get_coding_agent_status_text()
            status_summary = rigel.inference_with_memory(
                messages=[
                    ("system", f"{current_system_prompt}\n\nYou are the memory agent."),
                    ("human", f"Coding agent status: {status_text}\n\nReport this to the user in natural language."),
                ],
                thread_id=thread_id,
                RAG=False,
            )
            response_content = status_summary.content if hasattr(status_summary, "content") else str(status_summary)
        elif _has_call_coding_agent(response_content):
            coding_task = _extract_coding_agent_task(response_content)
            if coding_task:
                _spawn_background_coding_task(coding_task)
            notify = rigel.inference_with_memory(
                messages=[
                    ("system", f"{current_system_prompt}\n\nYou are the memory agent."),
                    ("human", f"The coding agent has started in background for task: '{coding_task or request.query}'. Inform the user briefly and naturally."),
                ],
                thread_id=thread_id,
                RAG=False,
            )
            response_content = notify.content if hasattr(notify, "content") else str(notify)

        if (not delegated) and _looks_like_capability_refusal(response_content):
            with concurrent.futures.ThreadPoolExecutor() as executor:
                tool_future = executor.submit(_execute_nl_tool_task, request.query, thread_id)
                tool_result = tool_future.result(timeout=120)

            tool_output_text = tool_result.content if hasattr(tool_result, "content") else str(tool_result)

            summarize_prompt = f"""
            {current_system_prompt}

            You are the memory agent.
            The tool agent has completed the task.
            Summarize the result for the user.

            Style rules:
            Use only natural language.
            Keep it short and concise whenever possible.
            No lists.
            No tutorials.
            No markdown.
            """

            summarized = rigel.inference_with_memory(
                messages=[
                    ("system", summarize_prompt),
                    ("human", f"User request: {request.query}\nSession context: {session_context}\nTool output: {tool_output_text}")
                ],
                thread_id=thread_id,
                RAG=False
            )
            response_content = summarized.content if hasattr(summarized, "content") else str(summarized)

        response_content = _sanitize_natural_language_output(response_content)
        _save_vector_session_turn(thread_id, request.query, response_content)

        duration_ms = int((time.time() - start_time) * 1000)
        tokens_estimated = (len(request.query.split()) + len(response_content.split())) * 3
        record_usage(tenant_info["tenant_id"], "rigel-natural-language", tokens_estimated, duration_ms)

        return QueryResponse(response=response_content)

    except concurrent.futures.TimeoutError:
        error_msg = "Natural language tool execution timed out after 2 minutes"
        syslog.error(error_msg)
        raise HTTPException(status_code=408, detail=error_msg)
    except Exception as e:
        error_msg = f"Error in rigel-natural-language flow: {str(e)}"
        syslog.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@app.post("/analyze-image", response_model=AnalyzeImageResponse)
async def analyze_image(request: AnalyzeImageRequest, tenant_info: Dict[str, Any] = Depends(require_api_key)):
    """Analyze an image using the vision engine."""
    global vision_engine

    await check_quotas_and_limits(tenant_info, "analyze-image")

    if vision_engine is None:
        vision_engine = get_vision_engine()

    if not os.path.exists(request.image_path):
        raise HTTPException(status_code=404, detail=f"Image file not found: {request.image_path}")

    try:
        result = vision_engine.analyze_image(request.image_path, request.prompt)
        if isinstance(result, dict):
            return AnalyzeImageResponse(result=result)
        return AnalyzeImageResponse(result={"analysis": result})
    except Exception as e:
        error_msg = f"Error analyzing image: {str(e)}"
        syslog.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@app.post("/synthesize-text", response_model=SynthesizeResponse)
async def synthesize_text(request: SynthesizeRequest, tenant_info: Dict[str, Any] = Depends(require_api_key)):
    """Convert text to speech with specified mode"""
    global synthesizer
    
    # Check quotas and rate limits
    await check_quotas_and_limits(tenant_info, "synthesize-text")
    
    start_time = time.time()
    
    try:
        syslog.info(f"SynthesizeText called with mode: {request.mode}, text length: {len(request.text)} by tenant {tenant_info['tenant_id']}")
        
        voice = request.voice or os.getenv("VOICE", "knight")
        if synthesizer is None:
            synthesizer = Synthesizer(mode=request.mode, voice=voice)
        else:
            synthesizer.mode = request.mode
            if request.voice:
                synthesizer.set_voice(request.voice)

        def _synthesize():
            synthesizer.synthesize(request.text)
        
        import threading
        synthesis_thread = threading.Thread(target=_synthesize)
        synthesis_thread.daemon = True
        synthesis_thread.start()
        
        # Record usage
        duration_ms = int((time.time() - start_time) * 1000)
        tokens_estimated = len(request.text.split())
        record_usage(tenant_info["tenant_id"], "synthesize-text", tokens_estimated, duration_ms)
        
        result = f"Text synthesis started successfully with mode: {request.mode}"
        return SynthesizeResponse(result=result)
        
    except Exception as e:
        error_msg = f"Error in text synthesis: {str(e)}"
        syslog.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@app.get("/list-voices")
async def list_voices(tenant_info: Dict[str, Any] = Depends(require_api_key)):
    """List available voice synthesis models"""
    try:
        voices = Synthesizer.list_available_voices()
        return {"voices": voices, "current": synthesizer.current_voice if synthesizer else os.getenv("VOICE", "knight")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/set-voice")
async def set_voice(request: SetVoiceRequest, tenant_info: Dict[str, Any] = Depends(require_api_key)):
    """Switch the active voice synthesis model"""
    global synthesizer
    try:
        if synthesizer is None:
            synthesizer = Synthesizer(mode="chunk", voice=request.voice)
        else:
            synthesizer.set_voice(request.voice)
        return {"status": "ok", "voice": synthesizer.current_voice}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/clone-voice")
async def clone_voice_endpoint(request: CloneVoiceRequest, tenant_info: Dict[str, Any] = Depends(require_api_key)):
    """Start voice cloning pipeline from an MP3 file"""
    try:
        from core.synth_n_recog import clone_voice as _clone_voice
        result = _clone_voice(
            request.mp3_path,
            request.voice_name,
            language=request.language,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/recognize-audio", response_model=RecognizeResponse)
async def recognize_audio(
    request: Request,
    audio_file: UploadFile = File(...),
    model: str = Form("tiny"),
    tenant_info: Dict[str, Any] = Depends(require_api_key),
):
    """Transcribe audio file to text"""
    global recognizer
    
    # Check quotas and rate limits
    client_host = request.client.host if request and request.client else None
    await check_quotas_and_limits(tenant_info, "recognize-audio", client_host=client_host)
    
    start_time = time.time()
    
    try:
        syslog.info(f"RecognizeAudio called with model: {model} by tenant {tenant_info['tenant_id']}")
        
        # Save uploaded file to temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
            content = await audio_file.read()
            tmp_file.write(content)
            tmp_file_path = tmp_file.name
        
        try:
            if recognizer is None:
                recognizer = Recognizer(model=model)
            elif hasattr(recognizer, 'model_name') and recognizer.model_name != model:
                recognizer = Recognizer(model=model)
                
            transcription = recognizer.transcribe(tmp_file_path)
            syslog.info(f"Transcription completed: {transcription[:100]}...")
            
            # Record usage
            duration_ms = int((time.time() - start_time) * 1000)
            tokens_estimated = len(transcription.split()) if transcription else 0
            record_usage(tenant_info["tenant_id"], "recognize-audio", tokens_estimated, duration_ms)
            
            return RecognizeResponse(transcription=transcription)
            
        finally:
            # Clean up temporary file
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)
            
    except Exception as e:
        error_msg = f"Error in audio recognition: {str(e)}"
        syslog.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@app.websocket("/live-voice-recognition")
async def live_voice_recognition(websocket: WebSocket):
    """WebSocket endpoint for live voice recognition.

    Client connects and sends:
      1. (optional) JSON config: {"model": "small.en", "threads": 8, ...}
      2. Binary audio frames (WAV format, 16kHz mono 16-bit recommended)

    Server responds with JSON messages:
      {"type": "ready", "message": "..."}
      {"type": "transcription", "text": "...", "partial": true/false}
      {"type": "error", "message": "..."}
      {"type": "done", "text": "final transcription"}

    The server accumulates audio and transcribes when the client disconnects
    or sends a JSON message with {"command": "transcribe"}.
    """
    global live_recognizer

    await websocket.accept()
    syslog.info("Live voice recognition WebSocket connected")

    accumulated_audio = bytearray()
    model = os.getenv("LIVE_VOICE_RECOGNITION_MODEL", "tiny.en")
    threads = 8
    tmp_path = None

    try:
        await websocket.send_json({"type": "ready", "message": "Live voice recognition ready", "model": model})

        while True:
            data = await websocket.receive()

            if "text" in data:
                # JSON control message
                try:
                    msg = json.loads(data["text"])
                except json.JSONDecodeError:
                    await websocket.send_json({"type": "error", "message": "Invalid JSON"})
                    continue

                if msg.get("command") == "transcribe":
                    if not accumulated_audio:
                        await websocket.send_json({"type": "transcription", "text": "", "partial": True})
                        continue

                    import tempfile
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                        tmp.write(bytes(accumulated_audio))
                        tmp_path = tmp.name

                    try:
                        lvr = LiveVoiceRecognizer(model=model, threads=threads)
                        transcription = lvr.transcribe_file(tmp_path)
                        await websocket.send_json({"type": "transcription", "text": transcription, "partial": True})
                    finally:
                        if tmp_path and os.path.exists(tmp_path):
                            os.unlink(tmp_path)
                            tmp_path = None

                elif msg.get("command") == "reset":
                    accumulated_audio = bytearray()
                    await websocket.send_json({"type": "ready", "message": "Audio buffer reset"})

                elif msg.get("command") == "config":
                    model = msg.get("model", model)
                    threads = msg.get("threads", threads)
                    await websocket.send_json({"type": "ready", "message": f"Config updated: model={model}, threads={threads}"})

            elif "bytes" in data:
                # Binary audio data
                chunk = data["bytes"]
                accumulated_audio.extend(chunk)

    except WebSocketDisconnect:
        syslog.info("Live voice recognition WebSocket disconnected")
    except Exception as e:
        syslog.error(f"Live voice recognition error: {e}")
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        # Transcribe remaining audio on disconnect
        if accumulated_audio:
            try:
                import tempfile
                with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                    tmp.write(bytes(accumulated_audio))
                    tmp_path = tmp.name

                lvr = LiveVoiceRecognizer(model=model, threads=threads)
                transcription = lvr.transcribe_file(tmp_path)
                try:
                    await websocket.send_json({"type": "done", "text": transcription})
                except Exception:
                    pass
            except Exception as e:
                syslog.error(f"Final transcription failed: {e}")
                try:
                    await websocket.send_json({"type": "error", "message": f"Final transcription failed: {str(e)}"})
                except Exception:
                    pass
            finally:
                if tmp_path and os.path.exists(tmp_path):
                    os.unlink(tmp_path)

@app.get("/license-info", response_model=LicenseResponse)
async def get_license_info():
    """Return license information for AGPL compliance - no auth required"""
    license_info = {
        "name": "RIGEL ENGINE",
        "version": VERSION,
        "license": "GNU Affero General Public License v3.0",
        "source": "https://github.com/Zerone-Laboratories/RIGEL",
        "copyright": "Copyright (C) 2025 Zerone Laboratories",
        "agpl_notice": "This program is free software under AGPL-3.0. If you run a modified version as a network service, you must provide source code to users."
    }
    return LicenseResponse(license_info=json.dumps(license_info, indent=2))


@app.get("/ui-admin-key")
async def ui_admin_key(request: Request):
    """Localhost-only helper for the built-in /ui page.

    This endpoint exists purely to improve local development UX.
    """
    client_host = request.client.host if request.client else ""
    if client_host not in {"127.0.0.1", "::1"}:
        raise HTTPException(status_code=404, detail="Not found")

    if not ADMIN_API_KEY:
        raise HTTPException(status_code=500, detail="Admin key not initialized")

    return {"admin_key": ADMIN_API_KEY}

# Admin endpoints
async def require_admin_key(x_admin_key: str = Header(None, alias="X-Admin-Key")):
    """FastAPI dependency for admin authentication"""
    if not ADMIN_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="Admin key not initialized. Server startup may have failed.",
        )
    if not x_admin_key or x_admin_key != ADMIN_API_KEY:
        raise HTTPException(
            status_code=403,
            detail="Admin access required. Please provide valid X-Admin-Key header."
        )
    return True

@app.post("/vectors/api/add")
async def ui_vectors_add(
    request: VectorAddRequest,
    _: bool = Depends(require_admin_key),
):
    collection = _get_ui_vectors_collection(request.collection or "ui_vectors")
    vector = _normalize_vector(request.vector, "vector")
    metadata = dict(request.metadata or {})
    metadata.setdefault("created_at", datetime.utcnow().isoformat())

    try:
        collection.upsert(
            ids=[request.id],
            embeddings=[vector],
            documents=[request.document or ""],
            metadatas=[metadata],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add vector: {str(e)}")

    return {"status": "ok", "id": request.id, "dimension": len(vector)}

@app.delete("/vectors/api/delete/{vector_id}")
async def ui_vectors_delete(
    vector_id: str,
    collection: str = "ui_vectors",
    _: bool = Depends(require_admin_key),
):
    collection = _get_ui_vectors_collection(collection)
    try:
        collection.delete(ids=[vector_id])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete vector: {str(e)}")
    return {"status": "ok", "deleted_id": vector_id}

@app.get("/vectors/api/list")
async def ui_vectors_list(
    collection: str = "ui_vectors",
    limit: int = 100,
    offset: int = 0,
    include_embeddings: bool = False,
    _: bool = Depends(require_admin_key),
):
    collection = _get_ui_vectors_collection(collection)
    include = ["documents", "metadatas"]
    if include_embeddings:
        include.append("embeddings")

    try:
        result = collection.get(limit=max(1, min(limit, 1000)), offset=max(0, offset), include=include)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list vectors: {str(e)}")

    ids = result.get("ids", []) or []
    documents = result.get("documents", []) or []
    metadatas = result.get("metadatas", []) or []
    embeddings = result.get("embeddings", []) or []

    items = []
    for i, vec_id in enumerate(ids):
        item = {
            "id": vec_id,
            "document": documents[i] if i < len(documents) else None,
            "metadata": metadatas[i] if i < len(metadatas) else None,
        }
        if include_embeddings and i < len(embeddings) and embeddings[i] is not None:
            emb = embeddings[i]
            item["dimension"] = len(emb)
            item["embedding_preview"] = emb[:8]
        items.append(item)

    return {"count": len(items), "items": items}

@app.post("/vectors/api/search")
async def ui_vectors_search(
    request: VectorSearchRequest,
    _: bool = Depends(require_admin_key),
):
    collection = _get_ui_vectors_collection(request.collection or "ui_vectors")
    query_vector = _normalize_vector(request.vector, "vector")
    top_k = max(1, min(int(request.top_k or 5), 100))

    try:
        result = collection.query(
            query_embeddings=[query_vector],
            n_results=top_k,
            include=["distances", "documents", "metadatas", "embeddings"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to search vectors: {str(e)}")

    ids = (result.get("ids") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]
    documents = (result.get("documents") or [[]])[0]
    metadatas = (result.get("metadatas") or [[]])[0]
    embeddings = (result.get("embeddings") or [[]])[0]

    hits = []
    for i, vec_id in enumerate(ids):
        item = {
            "id": vec_id,
            "distance": distances[i] if i < len(distances) else None,
            "document": documents[i] if i < len(documents) else None,
            "metadata": metadatas[i] if i < len(metadatas) else None,
        }
        if i < len(embeddings) and embeddings[i] is not None:
            try:
                item["cosine_similarity"] = _cosine_similarity(query_vector, embeddings[i])
            except HTTPException:
                item["cosine_similarity"] = None
        hits.append(item)

    return {
        "collection": request.collection or "ui_vectors",
        "query_dimension": len(query_vector),
        "top_k": top_k,
        "results": hits,
    }

@app.post("/vectors/api/search-text")
async def ui_vectors_search_text(
    request: VectorTextSearchRequest,
    _: bool = Depends(require_admin_key),
):
    collection_name = request.collection or "ui_vectors"
    collection = _get_ui_vectors_collection_for_text(collection_name)
    text = (request.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")
    top_k = max(1, min(int(request.top_k or 5), 100))

    try:
        query_embedding = _get_ui_embedding_function()([text])[0]
        result = collection.query(
            query_texts=[text],
            n_results=top_k,
            include=["distances", "documents", "metadatas", "embeddings"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to search vectors by text: {str(e)}")

    ids = (result.get("ids") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]
    documents = (result.get("documents") or [[]])[0]
    metadatas = (result.get("metadatas") or [[]])[0]
    embeddings = (result.get("embeddings") or [[]])[0]

    hits = []
    for i, vec_id in enumerate(ids):
        item = {
            "id": vec_id,
            "distance": distances[i] if i < len(distances) else None,
            "document": documents[i] if i < len(documents) else None,
            "metadata": metadatas[i] if i < len(metadatas) else None,
        }
        if i < len(embeddings) and embeddings[i] is not None:
            try:
                item["cosine_similarity"] = _cosine_similarity(query_embedding, embeddings[i])
            except HTTPException:
                item["cosine_similarity"] = None
        hits.append(item)

    return {
        "collection": collection_name,
        "query_text": text,
        "embedding_model": "chromadb DefaultEmbeddingFunction",
        "query_dimension": len(query_embedding),
        "top_k": top_k,
        "results": hits,
    }

@app.post("/vectors/api/cosine")
async def ui_vectors_cosine_similarity(
    request: VectorCosineRequest,
    _: bool = Depends(require_admin_key),
):
    collection = _get_ui_vectors_collection(request.collection or "ui_vectors")
    vector_a = request.vector_a
    vector_b = request.vector_b

    if request.id_a and vector_a is None:
        data_a = collection.get(ids=[request.id_a], include=["embeddings"])
        emb_a = data_a.get("embeddings", [])
        if not emb_a or emb_a[0] is None:
            raise HTTPException(status_code=404, detail=f"Vector not found for id_a={request.id_a}")
        vector_a = emb_a[0]

    if request.id_b and vector_b is None:
        data_b = collection.get(ids=[request.id_b], include=["embeddings"])
        emb_b = data_b.get("embeddings", [])
        if not emb_b or emb_b[0] is None:
            raise HTTPException(status_code=404, detail=f"Vector not found for id_b={request.id_b}")
        vector_b = emb_b[0]

    if vector_a is None or vector_b is None:
        raise HTTPException(
            status_code=400,
            detail="Provide vector_a and vector_b, or id_a and id_b, or mix of id and vector",
        )

    vector_a = _normalize_vector(vector_a, "vector_a")
    vector_b = _normalize_vector(vector_b, "vector_b")
    cosine = _cosine_similarity(vector_a, vector_b)
    return {
        "cosine_similarity": cosine,
        "dimension": len(vector_a),
        "id_a": request.id_a,
        "id_b": request.id_b,
        "collection": request.collection or "ui_vectors",
    }

@app.post("/vectors/api/records")
async def ui_vectors_create_record(
    request: RecordCreateRequest,
    _: bool = Depends(require_admin_key),
):
    collection_name = request.collection or "ui_vectors"
    collection = _get_ui_vectors_collection(collection_name)
    record_id = (request.id or "").strip() or str(uuid.uuid4())
    text = (request.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")

    embedding = _normalize_vector(request.vector, "vector") if request.vector is not None else _embed_text(text)
    now = datetime.utcnow().isoformat()
    metadata = dict(request.metadata or {})
    metadata.setdefault("created_at", now)
    metadata["updated_at"] = now

    try:
        collection.upsert(
            ids=[record_id],
            documents=[text],
            embeddings=[embedding],
            metadatas=[metadata],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create record: {str(e)}")

    return {"status": "ok", "id": record_id, "collection": collection_name, "dimension": len(embedding)}

@app.get("/vectors/api/records")
async def ui_vectors_list_records(
    collection: str = "ui_vectors",
    limit: int = 100,
    offset: int = 0,
    q: Optional[str] = None,
    _: bool = Depends(require_admin_key),
):
    coll = _get_ui_vectors_collection(collection)
    limit = max(1, min(limit, 1000))
    offset = max(0, offset)

    try:
        result = coll.get(limit=limit, offset=offset, include=["documents", "metadatas", "embeddings"])
        total = coll.count()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list records: {str(e)}")

    ids = result.get("ids", []) or []
    docs = result.get("documents", []) or []
    metas = result.get("metadatas", []) or []
    embs = result.get("embeddings", []) or []
    q_norm = (q or "").strip().lower()

    records = []
    for i, rid in enumerate(ids):
        text = docs[i] if i < len(docs) else ""
        if q_norm and q_norm not in (text or "").lower():
            continue
        emb = embs[i] if i < len(embs) else None
        records.append(
            {
                "id": rid,
                "text": text,
                "metadata": metas[i] if i < len(metas) else None,
                "dimension": len(emb) if emb is not None else None,
                "embedding_preview": emb[:6] if emb is not None else None,
            }
        )

    return {"collection": collection, "total": total, "count": len(records), "records": records}

@app.get("/vectors/api/records/{record_id}")
async def ui_vectors_get_record(
    record_id: str,
    collection: str = "ui_vectors",
    _: bool = Depends(require_admin_key),
):
    record_id = (record_id or "").strip()
    if not record_id:
        raise HTTPException(status_code=400, detail="record_id is required")
    coll = _get_ui_vectors_collection(collection)
    try:
        result = coll.get(ids=[record_id], include=["documents", "metadatas", "embeddings"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get record: {str(e)}")

    ids = result.get("ids", []) or []
    if not ids:
        raise HTTPException(status_code=404, detail="Record not found")

    docs = result.get("documents", []) or []
    metas = result.get("metadatas", []) or []
    embs = result.get("embeddings", []) or []
    emb = embs[0] if embs else None
    return {
        "collection": collection,
        "record": {
            "id": ids[0],
            "text": docs[0] if docs else "",
            "metadata": metas[0] if metas else None,
            "dimension": len(emb) if emb is not None else None,
            "embedding_preview": emb[:8] if emb is not None else None,
        },
    }

@app.put("/vectors/api/records/{record_id}")
async def ui_vectors_update_record(
    record_id: str,
    request: RecordUpdateRequest,
    _: bool = Depends(require_admin_key),
):
    record_id = (record_id or "").strip()
    if not record_id:
        raise HTTPException(status_code=400, detail="record_id is required")
    collection_name = request.collection or "ui_vectors"
    coll = _get_ui_vectors_collection(collection_name)

    def _first_or_none(value):
        if not value:
            return None
        first = value[0]
        if isinstance(first, list):
            return first[0] if first else None
        return first

    try:
        existing = coll.get(ids=[record_id], include=["documents", "metadatas"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read record: {str(e)}")

    ids = existing.get("ids", []) or []
    if not ids:
        raise HTTPException(status_code=404, detail="Record not found")

    old_text = str(_first_or_none(existing.get("documents")) or "").strip()
    old_meta = _first_or_none(existing.get("metadatas"))
    old_meta = old_meta if isinstance(old_meta, dict) else {}

    new_text = old_text if request.text is None else request.text.strip()
    if not new_text:
        raise HTTPException(status_code=400, detail="text cannot be empty")

    text_changed = request.text is not None and request.text.strip() != old_text

    if request.vector is not None:
        new_embedding = _normalize_vector(request.vector, "vector")
    elif text_changed:
        new_embedding = _embed_text(new_text)
    else:
        new_embedding = None

    new_meta = dict(old_meta)
    if request.metadata is not None:
        new_meta = dict(request.metadata)
    if "created_at" not in new_meta and isinstance(old_meta, dict) and old_meta.get("created_at"):
        new_meta["created_at"] = old_meta.get("created_at")
    new_meta["updated_at"] = datetime.utcnow().isoformat()

    update_payload = {
        "ids": [record_id],
        "documents": [new_text],
        "metadatas": [new_meta],
    }
    if new_embedding is not None:
        update_payload["embeddings"] = [new_embedding]

    try:
        coll.update(**update_payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update record: {str(e)}")

    return {
        "status": "ok",
        "id": record_id,
        "collection": collection_name,
        "dimension": len(new_embedding) if new_embedding is not None else None,
    }

@app.delete("/vectors/api/records/{record_id}")
async def ui_vectors_delete_record(
    record_id: str,
    collection: str = "ui_vectors",
    _: bool = Depends(require_admin_key),
):
    record_id = (record_id or "").strip()
    if not record_id:
        raise HTTPException(status_code=400, detail="record_id is required")
    coll = _get_ui_vectors_collection(collection)
    try:
        # Force a lookup first so delete returns a deterministic result for missing IDs.
        existing = coll.get(ids=[record_id])
        ids = existing.get("ids", []) or []
        if not ids:
            raise HTTPException(status_code=404, detail="Record not found")
        coll.delete(ids=[record_id])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete record: {str(e)}")
    return {"status": "ok", "deleted_id": record_id, "collection": collection}

@app.post("/vectors/api/records/search")
async def ui_vectors_search_records(
    request: RecordSearchRequest,
    _: bool = Depends(require_admin_key),
):
    collection_name = request.collection or "ui_vectors"
    coll = _get_ui_vectors_collection(collection_name)
    text = (request.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")
    top_k = max(1, min(int(request.top_k or 10), 100))
    query_embedding = _embed_text(text)

    try:
        result = coll.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["distances", "documents", "metadatas", "embeddings"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to search records: {str(e)}")

    ids = (result.get("ids") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]
    docs = (result.get("documents") or [[]])[0]
    metas = (result.get("metadatas") or [[]])[0]
    embs = (result.get("embeddings") or [[]])[0]

    records = []
    for i, rid in enumerate(ids):
        emb = embs[i] if i < len(embs) else None
        cosine = None
        if emb is not None:
            try:
                cosine = _cosine_similarity(query_embedding, emb)
            except HTTPException:
                cosine = None
        records.append(
            {
                "id": rid,
                "text": docs[i] if i < len(docs) else "",
                "metadata": metas[i] if i < len(metas) else None,
                "distance": distances[i] if i < len(distances) else None,
                "cosine_similarity": cosine,
            }
        )

    return {
        "collection": collection_name,
        "query_text": text,
        "embedding_model": "chromadb DefaultEmbeddingFunction",
        "query_dimension": len(query_embedding),
        "count": len(records),
        "records": records,
    }

@app.get("/vectors/api/databases")
async def ui_vectors_list_databases(
    include_counts: bool = True,
    _: bool = Depends(require_admin_key),
):
    db = _get_session_vector_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Vector database is unavailable")

    try:
        raw_collections = db.chroma_client.list_collections()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list databases: {str(e)}")

    databases = []
    for item in raw_collections:
        name = item.name if hasattr(item, "name") else str(item)
        row = {"name": name}
        if include_counts:
            try:
                row["count"] = db.chroma_client.get_collection(name=name).count()
            except Exception:
                row["count"] = None
        databases.append(row)

    return {"count": len(databases), "databases": databases}

@app.post("/admin/create-key", response_model=CreateKeyResponse)
async def create_new_api_key(
    request: CreateKeyRequest,
    _: bool = Depends(require_admin_key)
):
    """Create a new API key for a tenant"""
    try:
        api_key = create_api_key(request.name, request.plan)
        
        # Get the tenant info to return the ID
        tenant_info = get_tenant_info(api_key)
        if not tenant_info:
            raise HTTPException(status_code=500, detail="Failed to create API key")
        
        syslog.info(f"Created new API key for {request.name} with plan {request.plan}")
        
        return CreateKeyResponse(
            api_key=api_key,
            tenant_id=tenant_info["tenant_id"],
            plan=request.plan
        )
    except Exception as e:
        syslog.error(f"Error creating API key: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating API key: {str(e)}")

@app.get("/admin/usage/{tenant_id}", response_model=UsageStatsResponse)
async def get_usage_stats(
    tenant_id: int,
    _: bool = Depends(require_admin_key)
):
    """Get usage statistics for a tenant"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get tenant info
        cursor.execute("""
            SELECT name, plan, monthly_quota, daily_quota FROM tenants WHERE id = ?
        """, (tenant_id,))
        
        tenant_row = cursor.fetchone()
        if not tenant_row:
            conn.close()
            raise HTTPException(status_code=404, detail="Tenant not found")
        
        name, plan, monthly_quota, daily_quota = tenant_row
        
        # Get usage statistics
        cursor.execute("""
            SELECT COUNT(*) FROM usage 
            WHERE tenant_id = ? AND timestamp >= date('now', '-30 days')
        """, (tenant_id,))
        monthly_usage = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT COUNT(*) FROM usage 
            WHERE tenant_id = ? AND date(timestamp) = date('now')
        """, (tenant_id,))
        daily_usage = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT COUNT(*) FROM usage WHERE tenant_id = ?
        """, (tenant_id,))
        total_requests = cursor.fetchone()[0]
        
        conn.close()
        
        return UsageStatsResponse(
            tenant_id=tenant_id,
            name=name,
            plan=plan,
            monthly_usage=monthly_usage,
            monthly_quota=monthly_quota,
            daily_usage=daily_usage,
            daily_quota=daily_quota,
            total_requests=total_requests
        )
        
    except Exception as e:
        syslog.error(f"Error getting usage stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting usage stats: {str(e)}")

@app.get("/admin/list-tenants")
async def list_tenants(_: bool = Depends(require_admin_key)):
    """List all tenants - admin only"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, name, plan, active, created_at FROM tenants ORDER BY created_at DESC
        """)
        
        tenants = []
        for row in cursor.fetchall():
            tenants.append({
                "tenant_id": row[0],
                "name": row[1],
                "plan": row[2],
                "active": bool(row[3]),
                "created_at": row[4]
            })
        
        conn.close()
        return {"tenants": tenants}
        
    except Exception as e:
        syslog.error(f"Error listing tenants: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error listing tenants: {str(e)}")

@app.post("/admin/switch-inference-engine", response_model=InferenceEngineResponse)
async def switch_inference_engine(
    request: InferenceEngineRequest,
    _: bool = Depends(require_admin_key)
):
    """Switch the inference engine between GROQ, OLLAMA, and DEEPSEEK - admin only"""
    global inference_engine, rigel
    
    try:
        engine = request.engine.lower()
        if engine not in ["groq", "ollama", "deepseek"]:
            raise HTTPException(
                status_code=400, 
                detail="Invalid engine type. Must be 'groq', 'ollama', or 'deepseek'."
            )
        
        # Only reinitialize if the engine is changing
        if engine != inference_engine:
            inference_engine = engine
            await initialize_rigel()
            syslog.info(f"Switched inference engine to {inference_engine}")
        
        return InferenceEngineResponse(
            engine=inference_engine,
            status="Engine switched successfully"
        )
    except HTTPException:
        raise
    except Exception as e:
        syslog.error(f"Error switching inference engine: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error switching inference engine: {str(e)}")

@app.get("/admin/current-inference-engine", response_model=InferenceEngineResponse)
async def get_inference_engine(_: bool = Depends(require_admin_key)):
    """Get the current inference engine - admin only"""
    global inference_engine
    
    return InferenceEngineResponse(
        engine=inference_engine,
        status="Current engine"
    )


# ---------------------------------------------------------------------------
# CodingAgent endpoints (RigelClaude extension)
# ---------------------------------------------------------------------------

def _get_coding_agent():
    """Return the lazy-init RigelClaude singleton, or None if disabled."""
    return _get_or_create_coding_agent()

def _coding_agent_required():
    """FastAPI dependency — ensures RigelClaude is enabled."""
    agent = _get_coding_agent()
    if agent is None:
        raise HTTPException(
            status_code=503,
            detail="RigelClaude is not enabled. Set RIGEL_CLAUDE_ENABLED=true in .env",
        )
    return agent


@app.post("/coding-agent/generate-code", response_model=QueryResponse)
async def coding_agent_generate_code(
    request: CodingGenerateRequest,
    tenant_info: dict = Depends(require_api_key),
):
    agent = _coding_agent_required()
    result = agent.generate_code(request.specification, request.language)
    return QueryResponse(response=result)


@app.post("/coding-agent/review-code", response_model=QueryResponse)
async def coding_agent_review_code(
    request: CodingReviewRequest,
    tenant_info: dict = Depends(require_api_key),
):
    agent = _coding_agent_required()
    result = agent.review_code(request.code, request.language)
    return QueryResponse(response=result)


@app.post("/coding-agent/debug-code", response_model=QueryResponse)
async def coding_agent_debug_code(
    request: CodingDebugRequest,
    tenant_info: dict = Depends(require_api_key),
):
    agent = _coding_agent_required()
    result = agent.debug_code(request.code, request.error, request.language)
    return QueryResponse(response=result)


@app.post("/coding-agent/refactor-code", response_model=QueryResponse)
async def coding_agent_refactor_code(
    request: CodingRefactorRequest,
    tenant_info: dict = Depends(require_api_key),
):
    agent = _coding_agent_required()
    result = agent.refactor_code(request.code, request.instructions, request.language)
    return QueryResponse(response=result)


@app.post("/coding-agent/explain-code", response_model=QueryResponse)
async def coding_agent_explain_code(
    request: CodingExplainRequest,
    tenant_info: dict = Depends(require_api_key),
):
    agent = _coding_agent_required()
    result = agent.explain_code(request.code, request.language)
    return QueryResponse(response=result)


@app.post("/coding-agent/execute-code", response_model=QueryResponse)
async def coding_agent_execute_code(
    request: CodingExecuteRequest,
    tenant_info: dict = Depends(require_api_key),
):
    agent = _coding_agent_required()
    result = agent.execute_code_in_project(request.file_path, request.args)
    return QueryResponse(response=result)


@app.get("/coding-agent/status")
async def coding_agent_get_status(
    tenant_info: dict = Depends(require_api_key),
):
    agent = _coding_agent_required()
    return agent.get_status()


@app.get("/coding-agent/history")
async def coding_agent_get_history(
    last_n: int = 20,
    tenant_info: dict = Depends(require_api_key),
):
    agent = _coding_agent_required()
    return agent.get_coding_history(last_n=last_n)


@app.post("/coding-agent/launch")
async def coding_agent_launch(
    tenant_info: dict = Depends(require_api_key),
):
    agent = _coding_agent_required()
    return agent.launch()


@app.post("/coding-agent/close")
async def coding_agent_close(
    tenant_info: dict = Depends(require_api_key),
):
    agent = _coding_agent_required()
    return agent.close()


# Initialize RIGEL backend
async def initialize_rigel():
    """Initialize RIGEL backend and voice components"""
    global rigel, synthesizer, recognizer, live_recognizer, inference_engine, tools_rigel, tools_rigel_signature
    
    print("RIGEL Web Service")
    print("Copyright (C) 2025 Zerone Laboratories")
    print("Licensed under GNU Affero General Public License v3.0")
    print("This is free software; see the source for copying conditions.")
    print("")
    
    # Initialize MCP client (configurable via env var, fallback to localhost)
    tools_sse_url = get_tools_sse_url()
    default_mcp = MultiServerMCPClient(
        {
            "rigel tools": {
                "url": tools_sse_url,
                "transport": "sse",
            }
        },
    )
    
    if inference_engine == "ollama":
        # Check if Ollama is running and start it if not
        try:
            import requests
            import subprocess
            import time
            
            ollama_host = os.getenv("OLLAMA_HOST") or os.getenv("OLLAMA_URL") or "http://localhost:11434"

            # Try to connect to Ollama API
            try:
                response = requests.get(f"{ollama_host}/api/version", timeout=2)
                print(f"Ollama is already running, version: {response.json().get('version', 'unknown')}")
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
                print("Ollama is not running. Attempting to start Ollama server...")
                try:
                    # Start Ollama in the background
                    subprocess.Popen(["ollama", "serve"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    
                    # Wait for Ollama to start (with timeout)
                    start_time = time.time()
                    while time.time() - start_time < 30:  # 30 second timeout
                        try:
                            response = requests.get(f"{ollama_host}/api/version", timeout=2)
                            if response.status_code == 200:
                                print(f"Ollama started successfully, version: {response.json().get('version', 'unknown')}")
                                break
                        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
                            print("Waiting for Ollama to start...")
                            time.sleep(2)
                    else:
                        print("Warning: Timed out waiting for Ollama to start")
                except Exception as e:
                    print(f"Error starting Ollama: {e}")
                    print("Will attempt to continue, but RIGEL may not function correctly with Ollama backend")
                
            # Check if the required model is available
            model_name = "qwen3:0.6b"
            try:
                models_response = requests.get(f"{ollama_host}/api/tags", timeout=5)
                models = models_response.json().get('models', [])
                model_exists = any(model['name'] == model_name for model in models)
                
                if not model_exists:
                    print(f"Model {model_name} not found. Attempting to pull it (this may take some time)...")
                    # This is non-blocking to avoid hanging the server initialization
                    subprocess.Popen(["ollama", "pull", model_name], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    print(f"Started downloading {model_name} in the background")
                else:
                    print(f"Model {model_name} is already available")
            except Exception as e:
                print(f"Error checking/pulling Ollama model: {e}")
        except Exception as e:
            print(f"Error during Ollama setup: {e}")
        
        # Choose model from env: NORMAL_CHAT_MODEL > GENERAL_LLM_MODEL > OLLAMA_MODEL > default
        model_to_use = os.getenv("NORMAL_CHAT_MODEL") or os.getenv("GENERAL_LLM_MODEL") or os.getenv("OLLAMA_MODEL", "llama3.2")
        rigel = RigelOllama(model_name=model_to_use, mcp_endpoint=default_mcp)
        print("RIGEL initialized with OLLAMA backend")
        print("Initializing RIGEL Vector DB... [BACKGROUND]")
        # Initialize database in the background
        import threading
        db_init_thread = threading.Thread(target=rigel.readAndInitializeDatabase)
        db_init_thread.daemon = True
        db_init_thread.start()
        print("RIGEL Vector DB initialization started in background")

    elif inference_engine == "deepseek":
        # Choose model from env: NORMAL_CHAT_MODEL > GENERAL_LLM_MODEL > DEEPSEEK_MODEL > default
        model_to_use = os.getenv("NORMAL_CHAT_MODEL") or os.getenv("GENERAL_LLM_MODEL") or os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro")
        rigel = RigelDeepseek(model_name=model_to_use, mcp_endpoint=default_mcp)
        print("RIGEL initialized with DEEPSEEK backend")
        print("Initializing RIGEL Vector DB... [BACKGROUND]")
        import threading
        db_init_thread = threading.Thread(target=rigel.readAndInitializeDatabase)
        db_init_thread.daemon = True
        db_init_thread.start()
        print("RIGEL Vector DB initialization started in background")

    else:  # Default to GROQ
        # Choose model from env: NORMAL_CHAT_MODEL > GENERAL_LLM_MODEL > GROQ_MODEL > default
        model_to_use = os.getenv("NORMAL_CHAT_MODEL") or os.getenv("GENERAL_LLM_MODEL") or os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        rigel = RigelGroq(model_name=model_to_use, mcp_endpoint=default_mcp)
        print("RIGEL initialized with GROQ backend")
        print("Initializing RIGEL Vector DB... [BACKGROUND]")
        # Initialize database in the background
        import threading
        db_init_thread = threading.Thread(target=rigel.readAndInitializeDatabase)
        db_init_thread.daemon = True
        db_init_thread.start()
        print("RIGEL Vector DB initialization started in background")
    
    print("Initializing voice synthesis and recognition...")
    try:
        synthesizer = Synthesizer(mode="chunk", voice=os.getenv("VOICE", "knight"))
        recognizer = Recognizer(model=os.getenv("VOICE_RECOGNITION_MODEL", "tiny"))
        print("Voice components initialized successfully")
    except Exception as e:
        print(f"Warning: Failed to initialize voice components: {e}")
        print("Voice features may not be available")

    print("Initializing live voice recognition...")
    try:
        live_recognizer = LiveVoiceRecognizer(
            model=os.getenv("LIVE_VOICE_RECOGNITION_MODEL", "tiny.en")
        )
        print("Live voice recognition initialized successfully")
    except Exception as e:
        print(f"Warning: Failed to initialize live voice recognition: {e}")
        print("Live voice recognition features may not be available")

    tools_rigel = None
    tools_rigel_signature = None

if __name__ == "__main__":
    print("Starting RIGEL Web Server...")
    uvicorn.run(
        "web_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
