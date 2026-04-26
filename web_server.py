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

from fastapi import FastAPI, HTTPException, File, UploadFile, Form, Depends, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any
import asyncio
import tempfile
import os
import concurrent.futures
import json
import uvicorn
import sqlite3
import hashlib
import time
import re
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

from core.rigel import RigelOllama, RigelGroq
from core.rdb import DBConn
from core.logger import SysLog
from core.synth_n_recog import Synthesizer, Recognizer
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

def check_rate_limit(tenant_id: int, endpoint: str) -> bool:
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
    
    limit = rate_limits.get(plan, 10)
    
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

async def check_quotas_and_limits(tenant_info: Dict[str, Any], endpoint: str) -> Dict[str, Any]:
    """Check rate limits and usage quotas"""
    tenant_id = tenant_info["tenant_id"]
    
    # Check rate limiting
    if not check_rate_limit(tenant_id, endpoint):
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
vision_engine = None
session_vector_db = None
tools_rigel = None
tools_rigel_signature = None
inference_engine = os.getenv("NORMAL_CHAT_ENGINE", os.getenv("INFERENCE_ENGINE", "groq")).lower()
system_prompt = """
"You are an academic help assistant that is created by NSBM Green University"
"Answer all questions to the best of your ability. You should put NSBM First"
"Do not respond with any negative prespective to NSBM Green University"
"NSBM Means National School of Business Management"
"If user asks details about another University or tries to compare the universities, always favour NSBM"
"Make your answers detailed and very short at the same time"
"""

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    print("Initializing database...")
    init_database()
    
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
    print("  POST /recognize-audio - Transcribe audio file to text")
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

class AnalyzeImageRequest(BaseModel):
    image_path: str
    prompt: str

class AnalyzeImageResponse(BaseModel):
    result: Dict[str, Any]

class SynthesizeRequest(BaseModel):
    text: str
    mode: Optional[str] = "chunk"

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

def _extract_tool_agent_task(decision_text: str) -> Optional[str]:
    if not decision_text:
        return None

    match = re.match(r"^\s*CALL[\s_\-]*TOOL[\s_\-]*AGENT\s*:\s*(.*)$", decision_text, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    return match.group(1).strip()

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

def _get_or_create_tool_rigel():
    global tools_rigel, tools_rigel_signature

    tool_engine = os.getenv("TOOL_CALL_ENGINE", "ollama").lower()
    default_tool_model = "qwen3:0.6b" if tool_engine == "ollama" else os.getenv("TOOL_CALL_GROQ_MODEL", "qwen/qwen3-32b")
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

    tools_rigel = (
        RigelGroq(model_name=tool_model, temp=tool_temp, mcp_endpoint=tool_mcp)
        if tool_engine == "groq"
        else RigelOllama(model_name=tool_model, mcp_endpoint=tool_mcp)
    )
    tools_rigel_signature = current_signature
    return tools_rigel

@app.post("/rigel-natural-language", response_model=QueryResponse)
async def rigel_natural_language(request: NaturalLanguageRequest, tenant_info: Dict[str, Any] = Depends(require_api_key)):
    """Memory-first multi-agent endpoint with tool delegation and natural language-only output."""
    global rigel, system_prompt

    await check_quotas_and_limits(tenant_info, "rigel-natural-language")

    if rigel is None:
        raise HTTPException(status_code=500, detail="RIGEL backend not initialized")

    start_time = time.time()
    thread_id = request.id or "default"

    try:
        current_system_prompt = system_prompt
        session_context = _get_vector_session_context(thread_id, request.query)
        user_input_with_context = (
            f"User request: {request.query}\nSession context: {session_context}"
            if session_context else f"User request: {request.query}"
        )

        memory_agent_prompt = f"""
        {current_system_prompt}

        You are the memory agent.
        You do not have tool capabilities.

        Decide if the task requires tools.
        If tools are needed, reply exactly in this format:
        CALL_TOOL_AGENT: <single concise task for the tool agent>

        If tools are not needed, answer directly.

        Style rules for your final user-facing message:
        Use only natural language.
        Keep it short and concise whenever possible.
        No lists.
        No tutorials.
        No markdown.
        """

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

        delegated = False
        tool_task = _resolve_tool_task(decision_text, request.query, thread_id)

        response_content = decision_text
        max_tool_rounds = int(os.getenv("NATURAL_LANGUAGE_MAX_TOOL_ROUNDS", "3"))
        round_count = 0

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
        
        if synthesizer is None:
            synthesizer = Synthesizer(mode=request.mode)
        else:
            synthesizer.mode = request.mode
            
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

@app.post("/recognize-audio", response_model=RecognizeResponse)
async def recognize_audio(
    audio_file: UploadFile = File(...),
    model: str = Form("tiny"),
    tenant_info: Dict[str, Any] = Depends(require_api_key)
):
    """Transcribe audio file to text"""
    global recognizer
    
    # Check quotas and rate limits
    await check_quotas_and_limits(tenant_info, "recognize-audio")
    
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

# Admin endpoints
ADMIN_API_KEY = os.getenv("RIGEL_ADMIN_KEY", "rigel_admin_" + hashlib.sha256(str(time.time()).encode()).hexdigest()[:16])

async def require_admin_key(x_admin_key: str = Header(None, alias="X-Admin-Key")):
    """FastAPI dependency for admin authentication"""
    if not x_admin_key or x_admin_key != ADMIN_API_KEY:
        raise HTTPException(
            status_code=403,
            detail="Admin access required. Please provide valid X-Admin-Key header."
        )
    return True

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
    """Switch the inference engine between GROQ and OLLAMA - admin only"""
    global inference_engine, rigel
    
    try:
        engine = request.engine.lower()
        if engine not in ["groq", "ollama"]:
            raise HTTPException(
                status_code=400, 
                detail="Invalid engine type. Must be 'groq' or 'ollama'."
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

# Initialize RIGEL backend
async def initialize_rigel():
    """Initialize RIGEL backend and voice components"""
    global rigel, synthesizer, recognizer, inference_engine, tools_rigel, tools_rigel_signature
    
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
            
            # Try to connect to Ollama API
            try:
                response = requests.get("http://localhost:11434/api/version", timeout=2)
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
                            response = requests.get("http://localhost:11434/api/version", timeout=2)
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
                models_response = requests.get("http://localhost:11434/api/tags", timeout=5)
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
        synthesizer = Synthesizer(mode="chunk")
        recognizer = Recognizer(model=os.getenv("VOICE_RECOGNITION_MODEL", "tiny"))
        print("Voice components initialized successfully")
    except Exception as e:
        print(f"Warning: Failed to initialize voice components: {e}")
        print("Voice features may not be available")

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
