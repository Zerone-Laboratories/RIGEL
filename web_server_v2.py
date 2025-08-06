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

from fastapi import FastAPI, HTTPException, File, UploadFile, Form, Depends, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any
import asyncio
import tempfile
import os
import concurrent.futures
import json
import uvicorn
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
import secrets
import hashlib
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
import threading
import logging

from core.rigel import RigelOllama, RigelGroq
from core.logger import SysLog
from core.synth_n_recog import Synthesizer, Recognizer
from core.translation_core import Translator
from langchain_mcp_adapters.client import MultiServerMCPClient


class RigelWebServer:
    """Instanceable RIGEL Web Server with API key authentication and MongoDB integration"""
    
    def __init__(
        self,
        title: str = "RIGEL Web Service",
        version: str = "5.0.0",
        mongo_uri: str = None,
        mongo_db_name: str = "rigel_api",
        host: str = "0.0.0.0",
        port: int = 8000,
        log_level: str = "INFO"
    ):
        self.title = title
        self.version = version
        self.host = host
        self.port = port
        self.mongo_uri = mongo_uri or "mongodb+srv://zerone:NxVXKM6aXeNTjdDC@rigel-api.xdm3rfl.mongodb.net/?retryWrites=true&w=majority&appName=RIGEL-API"
        self.mongo_db_name = mongo_db_name
        
        # Initialize logging
        self.syslog = SysLog(name="RigelWebServerV2", level=log_level, log_file="server_v2.log")
        
        # Core components
        self.rigel = None
        self.synthesizer = None
        self.recognizer = None
        self.translator = None
        self.mongo_client = None
        self.db = None
        
        # Security
        self.security = HTTPBearer()
        
        # System prompt
        self.system_prompt = """
        You are RIGEL, a helpful assistant developed by Zerone Laboratories.
        """
        
        # Initialize FastAPI app
        self.app = self._create_app()
        
    def _create_app(self) -> FastAPI:
        """Create and configure FastAPI application"""
        
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            """Application lifespan manager"""
            # Startup
            await self._initialize_services()
            self.syslog.info("RIGEL Web Service V2 is running...")
            self._log_available_endpoints()
            
            yield
            
            # Shutdown
            await self._cleanup_services()
            self.syslog.info("RIGEL Web Service V2 shutting down...")
        
        app = FastAPI(
            title=self.title,
            description="Web API for RIGEL Engine V2 - An intelligent assistant with voice capabilities and API key authentication",
            version=self.version,
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
        
        # Enable CORS
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # Customize in production
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Register routes
        self._register_routes(app)
        
        return app
    
    def _register_routes(self, app: FastAPI):
        """Register all API routes"""
        
        # Public endpoints
        app.get("/")(self.root)
        app.post("/generate-api-key")(self.generate_api_key)
        app.get("/license-info")(self.get_license_info)
        
        # Protected endpoints (require API key)
        app.post("/query")(self.query)
        app.post("/query-with-memory")(self.query_with_memory)
        app.post("/query-think")(self.query_think)
        app.post("/query-with-tools")(self.query_with_tools)
        app.post("/translated-inference-with-memory")(self.translated_inference_with_memory)
        app.post("/synthesize-text")(self.synthesize_text)
        app.post("/recognize-audio")(self.recognize_audio)
        app.post("/translate-text")(self.translate_text)
        app.get("/api-key-info")(self.get_api_key_info)
        app.delete("/revoke-api-key")(self.revoke_api_key)
    
    async def _initialize_services(self):
        """Initialize all services"""
        self.syslog.info("RIGEL Web Service V2")
        self.syslog.info("Copyright (C) 2025 Zerone Laboratories")
        self.syslog.info("Licensed under GNU Affero General Public License v3.0")
        
        # Initialize MongoDB
        await self._initialize_mongodb()
        
        # Initialize RIGEL backend
        await self._initialize_rigel()
        
        # Initialize voice components
        await self._initialize_voice_components()
        
        # Initialize translation service
        await self._initialize_translation()
    
    async def _initialize_mongodb(self):
        """Initialize MongoDB connection"""
        try:
            self.mongo_client = AsyncIOMotorClient(self.mongo_uri)
            self.db = self.mongo_client[self.mongo_db_name]
            
            # Test connection
            await self.mongo_client.admin.command('ping')
            self.syslog.info("MongoDB connection established successfully")
            
            # Create indexes for API keys collection
            await self.db.api_keys.create_index("key_hash", unique=True)
            await self.db.api_keys.create_index("created_at")
            await self.db.api_keys.create_index("expires_at")
            
        except Exception as e:
            self.syslog.error(f"Failed to initialize MongoDB: {e}")
            raise
    
    async def _initialize_rigel(self):
        """Initialize RIGEL backend"""
        try:
            # Initialize MCP client
            default_mcp = MultiServerMCPClient({
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
            })
            
            self.rigel = RigelGroq(model_name="llama-3.3-70b-versatile", mcp_endpoint=default_mcp)
            self.syslog.info("RIGEL initialized with GROQ backend")
            
            self.syslog.info("Initializing VectorStore...")
            self.rigel.readAndInitializeDatabase()
            self.syslog.info("VectorStore initialized successfully")
            
        except Exception as e:
            self.syslog.error(f"Failed to initialize RIGEL: {e}")
            raise
    
    async def _initialize_voice_components(self):
        """Initialize voice synthesis and recognition"""
        try:
            self.synthesizer = Synthesizer(mode="chunk")
            self.recognizer = Recognizer(model="tiny")
            self.syslog.info("Voice components initialized successfully")
        except Exception as e:
            self.syslog.warning(f"Failed to initialize voice components: {e}")
            self.syslog.warning("Voice features may not be available")
    
    async def _initialize_translation(self):
        """Initialize translation service"""
        try:
            self.translator = Translator()
            self.syslog.info("Translation service initialized successfully")
        except Exception as e:
            self.syslog.warning(f"Failed to initialize translation service: {e}")
            self.syslog.warning("Translation features may not be available")
    
    async def _cleanup_services(self):
        """Cleanup services on shutdown"""
        if self.mongo_client:
            self.mongo_client.close()
            self.syslog.info("MongoDB connection closed")
    
    def _log_available_endpoints(self):
        """Log available endpoints"""
        endpoints = [
            "GET  /               - Service information",
            "POST /generate-api-key - Generate new API key",
            "GET  /license-info   - Display license information",
            "POST /query          - Basic inference (requires API key)",
            "POST /query-with-memory - Inference with memory (requires API key)",
            "POST /query-think    - Advanced thinking (requires API key)",
            "POST /query-with-tools - Inference with tools (requires API key)",
            "POST /translated-inference-with-memory - Italian conversation (requires API key)",
            "POST /synthesize-text - Text to speech (requires API key)",
            "POST /recognize-audio - Speech to text (requires API key)",
            "POST /translate-text - Text translation (requires API key)",
            "GET  /api-key-info   - Get API key information (requires API key)",
            "DELETE /revoke-api-key - Revoke API key (requires API key)"
        ]
        
        self.syslog.info("Available endpoints:")
        for endpoint in endpoints:
            self.syslog.info(f"  {endpoint}")
    
    async def _verify_api_key(self, credentials: HTTPAuthorizationCredentials) -> Dict[str, Any]:
        """Verify API key and return key info"""
        if not credentials or not credentials.credentials:
            raise HTTPException(status_code=401, detail="API key required")
        
        api_key = credentials.credentials
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
        # Look up API key in database
        key_doc = await self.db.api_keys.find_one({"key_hash": key_hash})
        
        if not key_doc:
            raise HTTPException(status_code=401, detail="Invalid API key")
        
        # Check if key is expired
        if key_doc.get("expires_at") and datetime.utcnow() > key_doc["expires_at"]:
            raise HTTPException(status_code=401, detail="API key expired")
        
        # Check if key is revoked
        if key_doc.get("revoked", False):
            raise HTTPException(status_code=401, detail="API key revoked")
        
        # Update last used timestamp
        await self.db.api_keys.update_one(
            {"_id": key_doc["_id"]},
            {"$set": {"last_used": datetime.utcnow()}}
        )
        
        return key_doc
    
    # Request/Response Models
    class GenerateApiKeyRequest(BaseModel):
        name: str
        description: Optional[str] = None
        expires_in_days: Optional[int] = None  # None = no expiration
    
    class GenerateApiKeyResponse(BaseModel):
        api_key: str
        key_id: str
        name: str
        created_at: datetime
        expires_at: Optional[datetime]
        message: str
    
    class QueryRequest(BaseModel):
        query: str
    
    class QueryWithMemoryRequest(BaseModel):
        query: str
        id: str
    
    class TranslatedInferenceWithMemoryRequest(BaseModel):
        query: str
        id: str
    
    class SynthesizeRequest(BaseModel):
        text: str
        mode: Optional[str] = "chunk"
    
    class TranslateRequest(BaseModel):
        text: str
        target_language: Optional[str] = "it"
        source_language: Optional[str] = "auto"
    
    class QueryResponse(BaseModel):
        response: str
    
    class SynthesizeResponse(BaseModel):
        result: str
    
    class RecognizeResponse(BaseModel):
        transcription: str
    
    class TranslateResponse(BaseModel):
        original_text: str
        translated_text: str
        source_language: str
        target_language: str
    
    class LicenseResponse(BaseModel):
        license_info: str
    
    class ApiKeyInfoResponse(BaseModel):
        key_id: str
        name: str
        description: Optional[str]
        created_at: datetime
        last_used: Optional[datetime]
        expires_at: Optional[datetime]
        usage_count: int
    
    # Route handlers
    async def root(self):
        """Root endpoint with service information"""
        return {
            "service": "RIGEL Web Service V2",
            "version": self.version,
            "copyright": "Copyright (C) 2025 Zerone Laboratories",
            "license": "GNU Affero General Public License v3.0",
            "authentication": "API key required for most endpoints",
            "endpoints": [
                "/generate-api-key",
                "/query",
                "/query-with-memory",
                "/query-think", 
                "/query-with-tools",
                "/translated-inference-with-memory",
                "/synthesize-text",
                "/recognize-audio",
                "/translate-text",
                "/api-key-info",
                "/revoke-api-key",
                "/license-info"
            ]
        }
    
    async def generate_api_key(self, request: GenerateApiKeyRequest):
        """Generate a new API key"""
        try:
            # Generate secure API key
            api_key = f"rigel_{secrets.token_urlsafe(32)}"
            key_hash = hashlib.sha256(api_key.encode()).hexdigest()
            
            # Calculate expiration date
            expires_at = None
            if request.expires_in_days:
                expires_at = datetime.utcnow() + timedelta(days=request.expires_in_days)
            
            # Create key document
            key_doc = {
                "key_hash": key_hash,
                "name": request.name,
                "description": request.description,
                "created_at": datetime.utcnow(),
                "expires_at": expires_at,
                "last_used": None,
                "usage_count": 0,
                "revoked": False
            }
            
            # Insert into database
            result = await self.db.api_keys.insert_one(key_doc)
            key_id = str(result.inserted_id)
            
            self.syslog.info(f"Generated new API key: {request.name} (ID: {key_id})")
            
            return self.GenerateApiKeyResponse(
                api_key=api_key,
                key_id=key_id,
                name=request.name,
                created_at=key_doc["created_at"],
                expires_at=expires_at,
                message="API key generated successfully. Store it securely - it cannot be retrieved again."
            )
            
        except Exception as e:
            self.syslog.error(f"Error generating API key: {e}")
            raise HTTPException(status_code=500, detail=f"Error generating API key: {str(e)}")
    
    async def query(self, request: QueryRequest, credentials: HTTPAuthorizationCredentials = Security(HTTPBearer())):
        """Basic inference endpoint"""
        key_doc = await self._verify_api_key(credentials)
        
        if not self.rigel:
            raise HTTPException(status_code=500, detail="RIGEL backend not initialized")
        
        try:
            messages = [
                ("system", self.system_prompt),
                ("human", request.query)
            ]
            response = self.rigel.inference(messages=messages)
            
            # Update usage count
            await self.db.api_keys.update_one(
                {"_id": key_doc["_id"]},
                {"$inc": {"usage_count": 1}}
            )
            
            return self.QueryResponse(response=response.content)
            
        except Exception as e:
            self.syslog.error(f"Error in query: {e}")
            raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")
    
    async def query_with_memory(self, request: QueryWithMemoryRequest, credentials: HTTPAuthorizationCredentials = Security(HTTPBearer())):
        """Inference with conversation memory"""
        key_doc = await self._verify_api_key(credentials)
        
        if not self.rigel:
            raise HTTPException(status_code=500, detail="RIGEL backend not initialized")
        
        try:
            messages = [
                ("system", self.system_prompt),
                ("human", request.query)
            ]
            response = self.rigel.inference_with_memory(messages=messages, thread_id=request.id)
            
            # Update usage count
            await self.db.api_keys.update_one(
                {"_id": key_doc["_id"]},
                {"$inc": {"usage_count": 1}}
            )
            
            return self.QueryResponse(response=response.content)
            
        except Exception as e:
            self.syslog.error(f"Error in query with memory: {e}")
            raise HTTPException(status_code=500, detail=f"Error processing query with memory: {str(e)}")
    
    async def query_think(self, request: QueryRequest, credentials: HTTPAuthorizationCredentials = Security(HTTPBearer())):
        """Advanced thinking capabilities"""
        key_doc = await self._verify_api_key(credentials)
        
        if not self.rigel:
            raise HTTPException(status_code=500, detail="RIGEL backend not initialized")
        
        try:
            response = self.rigel.think(request.query)
            
            # Update usage count
            await self.db.api_keys.update_one(
                {"_id": key_doc["_id"]},
                {"$inc": {"usage_count": 1}}
            )
            
            return self.QueryResponse(response=response)
            
        except Exception as e:
            self.syslog.error(f"Error in query think: {e}")
            raise HTTPException(status_code=500, detail=f"Error processing think query: {str(e)}")
    
    async def query_with_tools(self, request: QueryRequest, credentials: HTTPAuthorizationCredentials = Security(HTTPBearer())):
        """Inference with MCP tools support"""
        key_doc = await self._verify_api_key(credentials)
        
        if not self.rigel:
            raise HTTPException(status_code=500, detail="RIGEL backend not initialized")
        
        self.syslog.info(f"QueryWithTools called with query: {request.query[:100]}...")
        
        try:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(self._run_async_tools_query, request.query)
                result = future.result(timeout=120)
            
            response_content = result.content if hasattr(result, 'content') else str(result)
            
            # Update usage count
            await self.db.api_keys.update_one(
                {"_id": key_doc["_id"]},
                {"$inc": {"usage_count": 1}}
            )
            
            return self.QueryResponse(response=response_content)
            
        except concurrent.futures.TimeoutError:
            error_msg = "Query with tools timed out after 2 minutes"
            self.syslog.error(error_msg)
            raise HTTPException(status_code=408, detail=error_msg)
        except Exception as e:
            error_msg = f"Error occurred during tool-based inference: {str(e)}"
            self.syslog.error(error_msg)
            raise HTTPException(status_code=500, detail=error_msg)
    
    def _run_async_tools_query(self, query):
        """Helper function to run async tools query"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self.rigel.inference_with_tools(query))
        finally:
            loop.close()
    
    async def translated_inference_with_memory(self, request: TranslatedInferenceWithMemoryRequest, credentials: HTTPAuthorizationCredentials = Security(HTTPBearer())):
        """Inference with conversation memory in Italian"""
        key_doc = await self._verify_api_key(credentials)
        
        if not self.rigel:
            raise HTTPException(status_code=500, detail="RIGEL backend not initialized")
        
        if not self.translator:
            raise HTTPException(status_code=500, detail="Translation service not available")
        
        try:
            # Translate Italian to English
            english_query = await self.translator.translate_text(
                text=request.query,
                target_language="en",
                source_language="it"
            )
            
            # Process with RIGEL
            system_prompt = "You are an AI assistant designed to give information about restaurants. Your name is SARA"
            messages = [
                ("system", system_prompt),
                ("human", english_query)
            ]
            
            response = self.rigel.inference_with_memory(messages=messages, thread_id=request.id, RAG=True)
            
            # Translate response back to Italian
            italian_response = await self.translator.translate_text(
                text=response.content,
                target_language="it",
                source_language="en"
            )
            
            # Update usage count
            await self.db.api_keys.update_one(
                {"_id": key_doc["_id"]},
                {"$inc": {"usage_count": 1}}
            )
            
            return self.QueryResponse(response=italian_response)
            
        except Exception as e:
            error_msg = f"Error in translated inference with memory: {str(e)}"
            self.syslog.error(error_msg)
            raise HTTPException(status_code=500, detail=error_msg)
    
    async def synthesize_text(self, request: SynthesizeRequest, credentials: HTTPAuthorizationCredentials = Security(HTTPBearer())):
        """Convert text to speech"""
        key_doc = await self._verify_api_key(credentials)
        
        if not self.synthesizer:
            raise HTTPException(status_code=500, detail="Speech synthesis not available")
        
        try:
            self.syslog.info(f"SynthesizeText called with mode: {request.mode}, text length: {len(request.text)}")
            
            self.synthesizer.mode = request.mode
            
            def _synthesize():
                self.synthesizer.synthesize(request.text)
            
            synthesis_thread = threading.Thread(target=_synthesize)
            synthesis_thread.daemon = True
            synthesis_thread.start()
            
            # Update usage count
            await self.db.api_keys.update_one(
                {"_id": key_doc["_id"]},
                {"$inc": {"usage_count": 1}}
            )
            
            result = f"Text synthesis started successfully with mode: {request.mode}"
            return self.SynthesizeResponse(result=result)
            
        except Exception as e:
            error_msg = f"Error in text synthesis: {str(e)}"
            self.syslog.error(error_msg)
            raise HTTPException(status_code=500, detail=error_msg)
    
    async def recognize_audio(
        self,
        audio_file: UploadFile = File(...),
        model: str = Form("tiny"),
        credentials: HTTPAuthorizationCredentials = Security(HTTPBearer())
    ):
        """Transcribe audio file to text"""
        key_doc = await self._verify_api_key(credentials)
        
        if not self.recognizer:
            raise HTTPException(status_code=500, detail="Speech recognition not available")
        
        try:
            self.syslog.info(f"RecognizeAudio called with model: {model}")
            
            # Save uploaded file to temporary location
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
                content = await audio_file.read()
                tmp_file.write(content)
                tmp_file_path = tmp_file.name
            
            try:
                if hasattr(self.recognizer, 'model_name') and self.recognizer.model_name != model:
                    self.recognizer = Recognizer(model=model)
                
                transcription = self.recognizer.transcribe(tmp_file_path)
                self.syslog.info(f"Transcription completed: {transcription[:100]}...")
                
                # Update usage count
                await self.db.api_keys.update_one(
                    {"_id": key_doc["_id"]},
                    {"$inc": {"usage_count": 1}}
                )
                
                return self.RecognizeResponse(transcription=transcription)
                
            finally:
                if os.path.exists(tmp_file_path):
                    os.unlink(tmp_file_path)
                    
        except Exception as e:
            error_msg = f"Error in audio recognition: {str(e)}"
            self.syslog.error(error_msg)
            raise HTTPException(status_code=500, detail=error_msg)
    
    async def translate_text(self, request: TranslateRequest, credentials: HTTPAuthorizationCredentials = Security(HTTPBearer())):
        """Translate text from one language to another"""
        key_doc = await self._verify_api_key(credentials)
        
        if not self.translator:
            raise HTTPException(status_code=500, detail="Translation service not available")
        
        try:
            self.syslog.info(f"TranslateText called with target_language: {request.target_language}, source_language: {request.source_language}")
            
            translated_text = await self.translator.translate_text(
                text=request.text,
                target_language=request.target_language,
                source_language=request.source_language
            )
            
            # Update usage count
            await self.db.api_keys.update_one(
                {"_id": key_doc["_id"]},
                {"$inc": {"usage_count": 1}}
            )
            
            return self.TranslateResponse(
                original_text=request.text,
                translated_text=translated_text,
                source_language=request.source_language,
                target_language=request.target_language
            )
            
        except Exception as e:
            error_msg = f"Error in text translation: {str(e)}"
            self.syslog.error(error_msg)
            raise HTTPException(status_code=500, detail=error_msg)
    
    async def get_api_key_info(self, credentials: HTTPAuthorizationCredentials = Security(HTTPBearer())):
        """Get information about the current API key"""
        key_doc = await self._verify_api_key(credentials)
        
        return self.ApiKeyInfoResponse(
            key_id=str(key_doc["_id"]),
            name=key_doc["name"],
            description=key_doc.get("description"),
            created_at=key_doc["created_at"],
            last_used=key_doc.get("last_used"),
            expires_at=key_doc.get("expires_at"),
            usage_count=key_doc.get("usage_count", 0)
        )
    
    async def revoke_api_key(self, credentials: HTTPAuthorizationCredentials = Security(HTTPBearer())):
        """Revoke the current API key"""
        key_doc = await self._verify_api_key(credentials)
        
        # Mark key as revoked
        await self.db.api_keys.update_one(
            {"_id": key_doc["_id"]},
            {"$set": {"revoked": True, "revoked_at": datetime.utcnow()}}
        )
        
        self.syslog.info(f"API key revoked: {key_doc['name']} (ID: {key_doc['_id']})")
        
        return {"message": "API key revoked successfully"}
    
    async def get_license_info(self):
        """Return license information for AGPL compliance"""
        license_info = {
            "name": "RIGEL Engine",
            "version": self.version,
            "license": "GNU Affero General Public License v3.0",
            "source": "https://github.com/Zerone-Laboratories/RIGEL",
            "copyright": "Copyright (C) 2025 Zerone Laboratories",
            "agpl_notice": "This program is free software under AGPL-3.0. If you run a modified version as a network service, you must provide source code to users."
        }
        return self.LicenseResponse(license_info=json.dumps(license_info, indent=2))
    
    def run(self, reload: bool = False):
        """Run the web server"""
        self.syslog.info("Starting RIGEL Web Server V2...")
        
        if reload:
            # For reload mode, use import string
            uvicorn.run(
                "web_server_v2:app",
                host=self.host,
                port=self.port,
                reload=reload,
                log_level="info"
            )
        else:
            # For production mode, use app object directly
            uvicorn.run(
                self.app,
                host=self.host,
                port=self.port,
                reload=reload,
                log_level="info"
            )


# Factory function for creating server instances
def create_rigel_server(**kwargs) -> RigelWebServer:
    """Factory function to create a RIGEL server instance"""
    return RigelWebServer(**kwargs)


# Global app instance for uvicorn reload mode
app = None

def get_app():
    """Get or create the global app instance"""
    global app
    if app is None:
        server = create_rigel_server(
            title="RIGEL Web Service V2",
            version="5.0.0",
            port=8000
        )
        app = server.app
    return app

# Export app for uvicorn import
app = get_app()


if __name__ == "__main__":
    # Create and run server instance
    server = create_rigel_server(
        title="RIGEL Web Service V2",
        version="5.0.0",
        port=8000
    )
    
    server.run(reload=True)