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
from typing import Optional, Dict, Any, List
import asyncio
import tempfile
import os
import concurrent.futures
import json
import uvicorn
import sqlite3
import hashlib
import time
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

from core.rigel import RigelOllama, RigelGroq
from core.logger import SysLog
from core.synth_n_recog import Synthesizer, Recognizer
from core.mcp.cal_gpa import NSBMGPACalculator
from langchain_mcp_adapters.client import MultiServerMCPClient

# Initialize logging
syslog = SysLog(name="RigelWebServer", level="INFO", log_file="server.log")

# Database initialization
DB_PATH = "rigel_usage.db"

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
inference_engine = os.getenv("INFERENCE_ENGINE", "groq").lower()  # Default to groq, can be overridden
system_prompt = """
"You are an academic help assistant that is created by NSBM Green University"
"Answer all questions to the best of your ability. You should put NSBM First"
"Do not respond with any negative prespective to NSBM Green University"
"NSBM Means National School of Business Management"
"If user asks details about another University or tries to compare the universities, always favour NSBM"
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
    version="4.0.X",
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

class QueryWithMemoryRequest(BaseModel):
    query: str
    id: str
    RAG: Optional[str] = "false"

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

# NSBM GPA Calculation Models
class NSBMGPACalculationRequest(BaseModel):
    course_names: List[str]
    credits: List[float]
    grades: List[str]

class SimpleNSBMGPARequest(BaseModel):
    credits: List[float]
    grade_points: List[float]

class NSBMGradeInfoRequest(BaseModel):
    grade: str

class NSBMGPAResponse(BaseModel):
    gpa: float
    total_credits: float
    total_courses: int
    academic_standing: str
    grade_distribution: Dict[str, int]
    grading_system: str
    status: str
    improvement_suggestions: Optional[List[str]] = None
    courses: Optional[List[Dict]] = None

class NSBMGradeInfoResponse(BaseModel):
    input_grade: str
    gpa_points: float
    classification: str
    percentage_range: str
    status: str

# Routes
@app.get("/", response_model=dict)
async def root():
    """Root endpoint with service information - no auth required"""
    global inference_engine
    
    return {
        "service": "RIGEL Web Service",
        "version": "4.0.X",
        "copyright": "Copyright (C) 2025 Zerone Laboratories",
        "license": "GNU Affero General Public License v3.0",
        "current_inference_engine": inference_engine,
        "authentication": "API key required for all endpoints except root and license-info",
        "endpoints": [
            "/query",
            "/query-with-memory", 
            "/query-think",
            "/query-with-tools",
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
        messages = [
            ("system", f"{system_prompt}"),
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
        syslog.info(f"DEBUG: {request.RAG}")
        messages = [
            (
                "system",
                "" if request.RAG == "true" else system_prompt
            ),
            (
                "human", f"{request.query}"
            )
        ]
        if request.RAG == "true":
            RAG_Stat = True
        else:
            RAG_Stat = False
        syslog.info(f"DEBUG: RAGSTAT = {RAG_Stat}")
        
        response = rigel.inference_with_memory(messages=messages, thread_id=request.id, RAG=True)
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
    global rigel
    
    # Check quotas and rate limits
    await check_quotas_and_limits(tenant_info, "query-think")
    
    if rigel is None:
        raise HTTPException(status_code=500, detail="RIGEL backend not initialized")
    
    start_time = time.time()
    
    try:
        response = rigel.think(request.query)
        
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
    global rigel
    
    # Check quotas and rate limits
    await check_quotas_and_limits(tenant_info, "query-with-tools")
    
    if rigel is None:
        raise HTTPException(status_code=500, detail="RIGEL backend not initialized")
    
    syslog.info(f"QueryWithTools called with query: {request.query[:100]}... by tenant {tenant_info['tenant_id']}")
    
    start_time = time.time()
    
    try:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(_run_async_tools_query, request.query)
            result = future.result(timeout=120)
        
        if hasattr(result, 'content'):
            response_content = result.content
        else:
            response_content = str(result)
        
        # Record usage (tools use more resources, count as 3x tokens)
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

def _run_async_tools_query(query):
    """Helper function to run async tools query"""
    global rigel
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(rigel.inference_with_tools(query))
    finally:
        loop.close()

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
        "name": "RIGEL Enrigel.readAndInitializeDatabase()gine",
        "version": "4.0.X",
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

# NSBM GPA Calculation Endpoints
@app.post("/nsbm/gpa/calculate", response_model=NSBMGPAResponse)
async def calculate_nsbm_gpa(
    request: NSBMGPACalculationRequest,
    tenant_info: dict = Depends(require_api_key)
):
    """Calculate GPA for NSBM students with detailed analysis"""
    start_time = time.time()
    
    try:
        calculator = NSBMGPACalculator()
        
        # Validate input lengths
        if not (len(request.course_names) == len(request.credits) == len(request.grades)):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "All input lists must have the same length",
                    "course_count": len(request.course_names),
                    "credits_count": len(request.credits),
                    "grades_count": len(request.grades)
                }
            )
        
        # Add courses
        for name, credit, grade in zip(request.course_names, request.credits, request.grades):
            success = calculator.add_course(name, credit, grade)
            if not success:
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to add course: {name} with grade {grade}. Use NSBM letter grades (A+, A, A-, B+, B, B-, C+, C, C-, D+, D, F) or percentages (0-100)."
                )
        
        # Calculate results
        result = calculator.calculate_gpa()
        suggestions = calculator.get_nsbm_improvement_suggestions()
        
        if result['status'] == 'error':
            raise HTTPException(status_code=400, detail=result['message'])
        
        # Log usage
        duration_ms = int((time.time() - start_time) * 1000)
        record_usage(tenant_info['tenant_id'], "nsbm_gpa_calculate", 0, duration_ms)
        
        return NSBMGPAResponse(
            gpa=result['gpa'],
            total_credits=result['total_credits'],
            total_courses=result['total_courses'],
            academic_standing=result['academic_standing'],
            grade_distribution=result['grade_distribution'],
            grading_system=result['grading_system'],
            status=result['status'],
            improvement_suggestions=suggestions,
            courses=result['courses']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        syslog.error(f"Error calculating NSBM GPA: {str(e)}")
        raise HTTPException(status_code=500, detail=f"NSBM GPA calculation failed: {str(e)}")

@app.post("/nsbm/gpa/simple", response_model=Dict[str, Any])
async def calculate_simple_nsbm_gpa(
    request: SimpleNSBMGPARequest,
    tenant_info: dict = Depends(require_api_key)
):
    """Simple NSBM GPA calculation using credit hours and grade points"""
    start_time = time.time()
    
    try:
        calculator = NSBMGPACalculator()
        
        if len(request.credits) != len(request.grade_points):
            raise HTTPException(
                status_code=400,
                detail="Credits and grade points lists must have same length"
            )
        
        # Add courses with simple format
        for i, (credit, gp) in enumerate(zip(request.credits, request.grade_points)):
            if not (0 <= gp <= 4.0):
                raise HTTPException(
                    status_code=400,
                    detail=f"Grade point {gp} for course {i+1} must be between 0.0 and 4.0"
                )
            calculator.add_course(f"Course_{i+1}", credit, gp)
        
        result = calculator.calculate_gpa()
        
        # Log usage
        duration_ms = int((time.time() - start_time) * 1000)
        record_usage(tenant_info['tenant_id'], "nsbm_gpa_simple", 0, duration_ms)
        
        return {
            "gpa": result["gpa"],
            "total_credits": result["total_credits"],
            "academic_standing": result["academic_standing"],
            "grading_system": "NSBM University",
            "status": "success"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        syslog.error(f"Error calculating simple NSBM GPA: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Simple NSBM GPA calculation failed: {str(e)}")

@app.post("/nsbm/gpa/grade-info", response_model=NSBMGradeInfoResponse)
async def get_nsbm_grade_info(
    request: NSBMGradeInfoRequest,
    tenant_info: dict = Depends(require_api_key)
):
    """Get detailed information about NSBM grades and classifications"""
    start_time = time.time()
    
    try:
        calculator = NSBMGPACalculator()
        grade_info = calculator.get_nsbm_grade_info(request.grade)
        
        if grade_info['status'] == 'error':
            raise HTTPException(
                status_code=400,
                detail={
                    "input_grade": request.grade,
                    "error": grade_info['error'],
                    "suggestion": "Use NSBM letter grades (A+, A, A-, B+, B, B-, C+, C, C-, D+, D, F) or percentages (0-100)"
                }
            )
        
        # Log usage
        duration_ms = int((time.time() - start_time) * 1000)
        record_usage(tenant_info['tenant_id'], "nsbm_grade_info", 0, duration_ms)
        
        return NSBMGradeInfoResponse(
            input_grade=grade_info['input_grade'],
            gpa_points=grade_info['gpa_points'],
            classification=grade_info['classification'],
            percentage_range=grade_info['percentage_range'],
            status=grade_info['status']
        )
            
    except HTTPException:
        raise
    except Exception as e:
        syslog.error(f"Error getting NSBM grade info: {str(e)}")
        raise HTTPException(status_code=500, detail=f"NSBM grade info failed: {str(e)}")

@app.get("/nsbm/gpa/help")
async def get_nsbm_gpa_help():
    """Get help information about NSBM GPA calculation features"""
    return {
        "title": "NSBM University GPA Calculation API",
        "description": "Specialized GPA calculation endpoints for NSBM students",
        "endpoints": {
            "/nsbm/gpa/calculate": {
                "method": "POST",
                "description": "Calculate NSBM GPA with detailed analysis",
                "parameters": {
                    "course_names": "List of course names",
                    "credits": "List of credit hours for each course",
                    "grades": "List of NSBM grades (A+, A, A-, B+, B, B-, C+, C, C-, D+, D, F) or percentages (0-100)"
                }
            },
            "/nsbm/gpa/simple": {
                "method": "POST",
                "description": "Simple NSBM GPA calculation using grade points",
                "parameters": {
                    "credits": "List of credit hours",
                    "grade_points": "List of grade point values (0.0-4.0)"
                }
            },
            "/nsbm/gpa/grade-info": {
                "method": "POST",
                "description": "Get detailed NSBM grade information and classification",
                "parameters": {
                    "grade": "NSBM grade to analyze"
                }
            }
        },
        "nsbm_grading_scale": {
            "A+": {"gpa": 4.0, "percentage": "90-100%", "classification": "First Class Honours"},
            "A": {"gpa": 4.0, "percentage": "90-100%", "classification": "First Class Honours"},
            "A-": {"gpa": 3.7, "percentage": "85-89%", "classification": "First Class Honours"},
            "B+": {"gpa": 3.3, "percentage": "80-84%", "classification": "Second Class Honours - Upper"},
            "B": {"gpa": 3.0, "percentage": "75-79%", "classification": "Second Class Honours - Lower"},
            "B-": {"gpa": 2.7, "percentage": "70-74%", "classification": "Second Class Honours - Lower"},
            "C+": {"gpa": 2.3, "percentage": "65-69%", "classification": "General Pass"},
            "C": {"gpa": 2.0, "percentage": "60-64%", "classification": "General Pass"},
            "C-": {"gpa": 1.7, "percentage": "55-59%", "classification": "General Pass"},
            "D+": {"gpa": 1.3, "percentage": "50-54%", "classification": "General Pass"},
            "D": {"gpa": 1.0, "percentage": "45-49%", "classification": "General Pass"},
            "F": {"gpa": 0.0, "percentage": "0-44%", "classification": "Fail"}
        },
        "academic_classifications": {
            "First Class Honours": "GPA 3.7-4.0 - Excellent academic performance",
            "Second Class Honours - Upper": "GPA 3.3-3.69 - Very good academic performance", 
            "Second Class Honours - Lower": "GPA 3.0-3.29 - Good academic performance",
            "General Pass": "GPA 2.0-2.99 - Satisfactory academic performance",
            "Academic Probation": "GPA 1.0-1.99 - Below standard, improvement required",
            "Academic Dismissal Risk": "GPA below 1.0 - Serious academic difficulties"
        }
    }

# Initialize RIGEL backend
async def initialize_rigel():
    """Initialize RIGEL backend and voice components"""
    global rigel, synthesizer, recognizer, inference_engine
    
    print("RIGEL Web Service")
    print("Copyright (C) 2025 Zerone Laboratories")
    print("Licensed under GNU Affero General Public License v3.0")
    print("This is free software; see the source for copying conditions.")
    print("")
    
    # Initialize MCP client
    default_mcp = MultiServerMCPClient(
        {
            "rigel tools": {
                "url": "http://localhost:8001/sse",
                "transport": "sse",
            },
            "python-toolbox": {
                "command": "/home/zerone/Projects/NotMine/mcp_python_toolbox/.venv/bin/python",
                "args": [
                    "-m",
                    "mcp_python_toolbox",
                    "--workspace",
                    "/home/zerone/Documents/RIGEL_Data"
                ],
                "env": {
                    "PYTHONPATH": "/home/zerone/Projects/NotMine/mcp_python_toolbox/src",
                    "PATH": "/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
                    "VIRTUAL_ENV": "/home/zerone/Projects/NotMine/mcp_python_toolbox/.venv",
                    "PYTHONHOME": ""
                },
                "transport": "stdio"
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
            model_name = "llama3.2"
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
        
        rigel = RigelOllama(model_name="llama3.2", mcp_endpoint=default_mcp)
        print("RIGEL initialized with OLLAMA backend")
        print("Initializing RIGEL Vector DB...")
        rigel.readAndInitializeDatabase()
    else:  # Default to GROQ
        rigel = RigelGroq(model_name="", mcp_endpoint=default_mcp)
        print("RIGEL initialized with GROQ backend")
    
    print("Initializing voice synthesis and recognition...")
    try:
        synthesizer = Synthesizer(mode="chunk")
        recognizer = Recognizer(model="tiny")
        print("Voice components initialized successfully")
    except Exception as e:
        print(f"Warning: Failed to initialize voice components: {e}")
        print("Voice features may not be available")

if __name__ == "__main__":
    print("Starting RIGEL Web Server...")
    uvicorn.run(
        "web_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )