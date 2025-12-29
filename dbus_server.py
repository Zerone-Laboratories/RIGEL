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


from core.rigel import RigelOllama, RigelGroq
from pydbus import SessionBus, SystemBus
from gi.repository import GLib
import os
from core.logger import SysLog
from core.synth_n_recog import Synthesizer, Recognizer
import asyncio
import concurrent.futures
import os
import tempfile
from langchain_mcp_adapters.client import MultiServerMCPClient
from dotenv import load_dotenv
# Initialize logging
syslog = SysLog(name="RigelDBusServer", level="INFO", log_file="server.log")

# Load environment from .env (if present)
load_dotenv()

global rigel, system_prompt, synthesizer, recognizer
rigel = None
synthesizer = None
recognizer = None
system_prompt = """
You are RIGEL, a helpful assistant developed by Zerone Laboratories.
"""

class RigelServer(object):
    """
    <node>
        <interface name='com.rigel.RigelService'>
            <method name='Query'>
                <arg type='s' name='query' direction='in'/>
                <arg type='s' name='response' direction='out'/>
            </method>
            <method name='QueryWithMemory'>
                <arg type='s' name='query' direction='in'/>
                <arg type='s' name='id' direction='in'/>
                <arg type='s' name='RAG' direction='in'/>
                <arg type='s' name='response' direction='out'/>
            </method>
            <method name='QueryThink'>
                <arg type='s' name='query' direction='in'/>
                <arg type='s' name='response' direction='out'/>
            </method>
            <method name='QueryWithTools'>
                <arg type='s' name='query' direction='in'/>
                <arg type='s' name='response' direction='out'/>
            </method>
            <method name='SynthesizeText'>
                <arg type='s' name='text' direction='in'/>
                <arg type='s' name='mode' direction='in'/>
                <arg type='s' name='result' direction='out'/>
            </method>
            <method name='RecognizeAudio'>
                <arg type='s' name='audio_file_path' direction='in'/>
                <arg type='s' name='model' direction='in'/>
                <arg type='s' name='transcription' direction='out'/>
            </method>
            <method name='GetLicenseInfo'>
                <arg type='s' name='license_info' direction='out'/>
            </method>
        </interface>
    </node>
    """

    def GetLicenseInfo(self):
        """Return license information for AGPL compliance"""
        import json
        license_info = {
            "name": "RIGEL Engine",
            "version": "4.0.X",
            "license": "GNU Affero General Public License v3.0",
            "source": "https://github.com/Zerone-Laboratories/RIGEL",
            "copyright": "Copyright (C) 2025 Zerone Laboratories",
            "agpl_notice": "This program is free software under AGPL-3.0. If you run a modified version as a network service, you must provide source code to users."
        }
        return json.dumps(license_info, indent=2)

    def Query(self, query):
        global system_prompt, rigel
        messages = [
            (
                "system",
                f"{system_prompt}"
            ),
            (
                "human", f"{query}"
            )
        ]
        response = rigel.inference(messages=messages)
        # print(response)
        return response.content

    def QueryWithMemory(self, query, id, RAG):
        global system_prompt, rigel
        print(f"DEBUG: {RAG}")
        messages = [
            (
                "system",
                "" if RAG == '"true"' else system_prompt
            ),
            (
                "human", f"{query}"
            )
        ]
        if RAG=='"true"':
            RAG_Stat = True
        else:
            RAG_Stat = False
        print(f"DEBUG: RAGSTAT = {RAG_Stat}")
        response = rigel.inference_with_memory(messages=messages, thread_id=id, RAG=RAG_Stat)
        # print(response)
        return response.content

    def QueryThink(self, query):
        global rigel
        response = rigel.think(query)
        return response

    def QueryWithTools(self, query):
        # Configure tool-call backend and model via environment
        tool_engine = os.getenv("TOOL_CALL_ENGINE", os.getenv("INFERENCE_ENGINE", "ollama")).lower()
        default_tool_model = "qwen3:0.6b" if tool_engine == "ollama" else os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
        tool_model = os.getenv("TOOL_CALL_MODEL", default_tool_model)
        tool_temp = float(os.getenv("TOOL_TEMPERATURE", os.getenv("TEMPERATURE", "0.0")))

        rigel_agent = (
            RigelGroq(model_name=tool_model, temp=tool_temp)
            if tool_engine == "groq"
            else RigelOllama(model_name=tool_model, temp=tool_temp)
        )

        syslog.info(f"QueryWithTools called with query: {query[:100]}...")
        try:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(self._run_async_tools_query, query, rigel_agent)
                result = future.result(timeout=120)

            if hasattr(result, 'content'):
                return result.content
            else:
                return str(result)

        except concurrent.futures.TimeoutError:
            error_msg = "Query with tools timed out after 2 minutes"
            syslog.error(error_msg)
            return f"Error: {error_msg}"
        except Exception as e:
            error_msg = f"Error occurred during tool-based inference: {str(e)}"
            syslog.error(error_msg)
            return f"Error: {error_msg}"

    def _run_async_tools_query(self, query, rigel):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(rigel.inference_with_tools(query))
        finally:
            loop.close()

    def SynthesizeText(self, text, mode="chunk"):
        global synthesizer

        try:
            syslog.info(f"SynthesizeText called with mode: {mode}, text length: {len(text)}")

            if synthesizer is None:
                synthesizer = Synthesizer(mode=mode)
            else:
                synthesizer.mode = mode
            def _synthesize():
                synthesizer.synthesize(text)

            import threading
            synthesis_thread = threading.Thread(target=_synthesize)
            synthesis_thread.daemon = True
            synthesis_thread.start()

            return f"Text synthesis started successfully with mode: {mode}"

        except Exception as e:
            error_msg = f"Error in text synthesis: {str(e)}"
            syslog.error(error_msg)
            return error_msg

    def RecognizeAudio(self, audio_file_path, model="tiny"):
        global recognizer

        try:
            syslog.info(f"RecognizeAudio called with file: {audio_file_path}, model: {model}")
            if not os.path.exists(audio_file_path):
                return f"Error: Audio file not found: {audio_file_path}"
            if recognizer is None:
                recognizer = Recognizer(model=model)
            elif hasattr(recognizer, 'model_name') and recognizer.model_name != model:
                recognizer = Recognizer(model=model)
            transcription = recognizer.transcribe(audio_file_path)
            syslog.info(f"Transcription completed: {transcription[:100]}...")

            return transcription

        except Exception as e:
            error_msg = f"Error in audio recognition: {str(e)}"
            syslog.error(error_msg)
            return error_msg


if __name__ == "__main__":
    print("RIGEL DBUS Interface")
    print("Copyright (C) 2025 Zerone Laboratories")
    print("Licensed under GNU Affero General Public License v3.0")
    print("This is free software; see the source for copying conditions.")
    print("")
    default_mcp = None
    # How to add an MCP server
    tools_sse_url = os.environ.get("RIGEL_MCP_TOOLS_SSE_URL", "http://localhost:8001/sse")
    default_mcp = MultiServerMCPClient(
        {
            "rigel tools": {
                "url": tools_sse_url,
                "transport": "sse",
            },
        },
    )
    if default_mcp == None:
        print("""Open server.py and add your custom mcp servers here before initializing
              There is a basic mcp server built in inside core/mcp/rigel_tools_server.py
              You can start it by typing
              python core/mcp/rigel_tools_server.py
              """)
    
    # Get backend and model from environment
    inference_engine = os.environ.get("INFERENCE_ENGINE", "ollama").lower()
    # Prefer GENERAL_LLM_MODEL, then backend-specific default, then hardcoded fallback
    general_model = os.getenv("GENERAL_LLM_MODEL")
    if inference_engine == "groq":
        model_to_use = general_model or os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
        rigel = RigelGroq(model_name=model_to_use, mcp_endpoint=default_mcp)
        print("RIGEL initialized with GROQ backend")
    else:
        model_to_use = general_model or os.getenv("OLLAMA_MODEL", "llama3.2")
        rigel = RigelOllama(model_name=model_to_use, mcp_endpoint=default_mcp)
        print("RIGEL initialized with OLLAMA backend")


    print("Initializing Vector Database...")
    rigel.readAndInitializeDatabase()

    # Initialize voice components
    print("Initializing voice synthesis and recognition...")
    try:
        synthesizer = Synthesizer(mode="chunk")
        recognizer = Recognizer(model=os.getenv("VOICE_RECOGNITION_MODEL", "tiny"))
        print("Voice components initialized successfully")
    except Exception as e:
        print(f"Warning: Failed to initialize voice components: {e}")
        print("Voice features may not be available")

    # Determine which bus to use - try SessionBus first, fall back to SystemBus in Docker environments
    try:
        print("Attempting to connect to Session Bus...")
        bus = SessionBus()
        print("Successfully connected to Session Bus")
    except Exception as e:
        print(f"Session Bus connection failed: {e}")
        print("Attempting to connect to System Bus instead...")
        try:
            bus = SystemBus()
            print("Successfully connected to System Bus")
        except Exception as e:
            print(f"System Bus connection failed too: {e}")
            print("Error: Could not connect to any D-Bus. Ensure D-Bus is properly configured.")
            exit(1)
            
    bus.publish("com.rigel.RigelService", RigelServer())

    print("RIGEL D-Bus service is running...")
    print("Service name: com.rigel.RigelService")
    print("Interface: com.rigel.RigelService")
    print("Available Methods:")
    print("  - Query: Basic inference")
    print("  - QueryWithMemory: Inference with conversation memory")
    print("  - QueryThink: Advanced thinking capabilities")
    print("  - QueryWithTools: Inference with MCP tools support")
    print("  - SynthesizeText: Convert text to speech with specified mode")
    print("  - RecognizeAudio: Transcribe audio file to text")
    print("  - SynthesizeAndSpeak: Quick text-to-speech conversion and playback")
    print("  - GetLicenseInfo: Display license and copyright information")
    print("Press Ctrl+C to stop")

    loop = GLib.MainLoop()
    try:
        loop.run()
    except KeyboardInterrupt:
        print("\nStopping RIGEL D-Bus service...")
        loop.quit()
