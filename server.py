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


from pydbus import SessionBus
from gi.repository import GLib
from core.rigel import RigelOllama, RigelGroq
from core.logger import SysLog
from core.synth_n_recog import Synthesizer, Recognizer
import asyncio
import concurrent.futures
import os
import tempfile
# Initialize logging
syslog = SysLog(name="RigelDBusServer", level="INFO", log_file="server.log")

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

    def QueryWithMemory(self, query, id):
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
        response = rigel.inference_with_memory(messages=messages, thread_id=id)
        # print(response)
        return response.content
    
    def QueryThink(self, query):
        global rigel
        response = rigel.inference(messages=query)
        return response
    
    def QueryWithTools(self, query):
        global rigel
        
        syslog.info(f"QueryWithTools called with query: {query[:100]}...")
        try:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(self._run_async_tools_query, query)
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
    
    def _run_async_tools_query(self, query):
        global rigel
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
    print("Select Required Backend :")
    backend_choice = int(input("Select '1' for GROQ and '2' for OLLAMA "))
    
    if backend_choice == 1:
        rigel = RigelGroq()
        print("RIGEL initialized with GROQ backend")
    else:
        rigel = RigelOllama()
        print("RIGEL initialized with OLLAMA backend")

    # Initialize voice components
    print("Initializing voice synthesis and recognition...")
    try:
        synthesizer = Synthesizer(mode="chunk")
        recognizer = Recognizer(model="tiny")
        print("Voice components initialized successfully")
    except Exception as e:
        print(f"Warning: Failed to initialize voice components: {e}")
        print("Voice features may not be available")

    bus = SessionBus()
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