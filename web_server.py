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

from fastapi import FastAPI, HTTPException, File, UploadFile, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
import asyncio
import tempfile
import os
import concurrent.futures
import json
import uvicorn
from contextlib import asynccontextmanager

from core.rigel import RigelOllama, RigelGroq
from core.logger import SysLog
from core.synth_n_recog import Synthesizer, Recognizer
from langchain_mcp_adapters.client import MultiServerMCPClient

# Initialize logging
syslog = SysLog(name="RigelWebServer", level="INFO", log_file="server.log")

# Global variables
rigel = None
synthesizer = None
recognizer = None
system_prompt = """
You are RIGEL, a helpful assistant developed by Zerone Laboratories.
"""

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
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

# Routes
@app.get("/", response_model=dict)
async def root():
    """Root endpoint with service information"""
    return {
        "service": "RIGEL Web Service",
        "version": "4.0.X",
        "copyright": "Copyright (C) 2025 Zerone Laboratories",
        "license": "GNU Affero General Public License v3.0",
        "endpoints": [
            "/query",
            "/query-with-memory", 
            "/query-think",
            "/query-with-tools",
            "/synthesize-text",
            "/recognize-audio",
            "/license-info"
        ]
    }

@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """Basic inference endpoint"""
    global system_prompt, rigel
    
    if rigel is None:
        raise HTTPException(status_code=500, detail="RIGEL backend not initialized")
    
    try:
        messages = [
            ("system", f"{system_prompt}"),
            ("human", f"{request.query}")
        ]
        response = rigel.inference(messages=messages)
        return QueryResponse(response=response.content)
    except Exception as e:
        syslog.error(f"Error in query: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")

@app.post("/query-with-memory", response_model=QueryResponse)
async def query_with_memory(request: QueryWithMemoryRequest):
    """Inference with conversation memory"""
    global system_prompt, rigel
    
    if rigel is None:
        raise HTTPException(status_code=500, detail="RIGEL backend not initialized")
    
    try:
        messages = [
            ("system", f"{system_prompt}"),
            ("human", f"{request.query}")
        ]
        response = rigel.inference_with_memory(messages=messages, thread_id=request.id)
        return QueryResponse(response=response.content)
    except Exception as e:
        syslog.error(f"Error in query with memory: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing query with memory: {str(e)}")

@app.post("/query-think", response_model=QueryResponse)
async def query_think(request: QueryRequest):
    """Advanced thinking capabilities"""
    global rigel
    
    if rigel is None:
        raise HTTPException(status_code=500, detail="RIGEL backend not initialized")
    
    try:
        response = rigel.think(request.query)
        return QueryResponse(response=response)
    except Exception as e:
        syslog.error(f"Error in query think: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing think query: {str(e)}")

@app.post("/query-with-tools", response_model=QueryResponse)
async def query_with_tools(request: QueryRequest):
    """Inference with MCP tools support"""
    global rigel
    
    if rigel is None:
        raise HTTPException(status_code=500, detail="RIGEL backend not initialized")
    
    syslog.info(f"QueryWithTools called with query: {request.query[:100]}...")
    
    try:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(_run_async_tools_query, request.query)
            result = future.result(timeout=120)
        
        if hasattr(result, 'content'):
            response_content = result.content
        else:
            response_content = str(result)
            
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
async def synthesize_text(request: SynthesizeRequest):
    """Convert text to speech with specified mode"""
    global synthesizer
    
    try:
        syslog.info(f"SynthesizeText called with mode: {request.mode}, text length: {len(request.text)}")
        
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
        
        result = f"Text synthesis started successfully with mode: {request.mode}"
        return SynthesizeResponse(result=result)
        
    except Exception as e:
        error_msg = f"Error in text synthesis: {str(e)}"
        syslog.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@app.post("/recognize-audio", response_model=RecognizeResponse)
async def recognize_audio(
    audio_file: UploadFile = File(...),
    model: str = Form("tiny")
):
    """Transcribe audio file to text"""
    global recognizer
    
    try:
        syslog.info(f"RecognizeAudio called with model: {model}")
        
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
    """Return license information for AGPL compliance"""
    license_info = {
        "name": "RIGEL Engine",
        "version": "4.0.X",
        "license": "GNU Affero General Public License v3.0",
        "source": "https://github.com/Zerone-Laboratories/RIGEL",
        "copyright": "Copyright (C) 2025 Zerone Laboratories",
        "agpl_notice": "This program is free software under AGPL-3.0. If you run a modified version as a network service, you must provide source code to users."
    }
    return LicenseResponse(license_info=json.dumps(license_info, indent=2))

# Initialize RIGEL backend
async def initialize_rigel():
    """Initialize RIGEL backend and voice components"""
    global rigel, synthesizer, recognizer
    
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
    
    rigel = RigelGroq(model_name="llama-3.3-70b-versatile", mcp_endpoint=default_mcp)
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