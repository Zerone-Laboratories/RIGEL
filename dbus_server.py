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
from core.extensions.rigel_claude_code_integration import RigelClaude
import os
_RIGEL_CLAUDE_ENABLED = os.getenv("RIGEL_CLAUDE_ENABLED", "false").lower() == "true"
from pydbus import SessionBus, SystemBus
from gi.repository import GLib
import subprocess
import threading
import queue
from core.logger import SysLog
from core.synth_n_recog import Synthesizer, Recognizer, LiveVoiceRecognizer
from core.vision import VisionEngine, get_vision_engine
from core.rdb import DBConn
import asyncio
from version import VERSION
import concurrent.futures
import tempfile
import json
import re
import uuid
from typing import Optional
from datetime import datetime
import urllib.request
import urllib.error
from langchain_mcp_adapters.client import MultiServerMCPClient
from dotenv import load_dotenv

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

syslog = SysLog(name="RigelDBusServer", level="INFO", log_file="server.log")

load_dotenv()

MCP_SERVER_URL = os.environ.get("RIGEL_MCP_TOOLS_URL", "http://172.17.0.1:8002")


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

def call_mcp_tool(tool_name: str, arguments: dict = None, timeout: int = 60) -> dict:
    """Call an MCP tool via HTTP POST request"""
    try:
        url = f"{MCP_SERVER_URL}/call-tool"
        payload = json.dumps({
            "name": tool_name,
            "arguments": arguments or {}
        }).encode('utf-8')

        req = urllib.request.Request(
            url,
            data=payload,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )

        with urllib.request.urlopen(req, timeout=timeout) as response:
            result = json.loads(response.read().decode('utf-8'))
            # MCP returns content array, extract text
            if isinstance(result, dict) and 'content' in result:
                for item in result['content']:
                    if item.get('type') == 'text':
                        try:
                            return json.loads(item['text'])
                        except:
                            return {"result": item['text']}
            return result
    except urllib.error.URLError as e:
        return {"status": "error", "message": f"MCP server connection failed: {str(e)}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

load_dotenv()

def _get_env_system_prompt(default_prompt: str) -> str:
    prompt = os.getenv("RIGEL_SYSTEM_PROMPT")
    if prompt:
        return prompt.replace("\\n", "\n")
    return default_prompt


def _synthesis_worker_loop():
    global synthesizer
    syslog.info("Synthesis worker thread started")
    while True:
        try:
            request = synthesis_queue.get(timeout=1)
        except queue.Empty:
            continue

        if not isinstance(request, dict):
            syslog.warning("Ignoring invalid synthesis queue item")
            synthesis_queue.task_done()
            continue

        text = request.get("text")
        mode = request.get("mode", "chunk")
        if text is None:
            synthesis_queue.task_done()
            continue

        try:
            syslog.info(
                f"Processing queued synthesis request: mode={mode}, text length={len(text)}"
            )
            if synthesizer is None:
                synthesizer = Synthesizer(mode=mode)
            else:
                synthesizer.mode = mode
            synthesizer.synthesize(text)
            syslog.info("Queued synthesis request completed")
        except Exception as e:
            syslog.error(f"Error processing queued synthesis request: {e}")
        finally:
            synthesis_queue.task_done()


def _ensure_synthesis_worker_running():
    global synthesis_worker_thread
    if synthesis_worker_thread is None or not synthesis_worker_thread.is_alive():
        synthesis_worker_thread = threading.Thread(
            target=_synthesis_worker_loop,
            daemon=True,
        )
        synthesis_worker_thread.start()


global rigel, system_prompt, synthesizer, recognizer, vision_engine, browser_state, synthesis_queue, synthesis_worker_thread, live_recognizer, _coding_agent_background_task
rigel = None
synthesizer = None
recognizer = None
vision_engine = None
live_recognizer = None
_coding_agent_background_task = None  # {"query": str, "start_time": str, "thread": Thread}
_coding_agent = None  # lazy-init RigelClaude singleton
browser_state = {"playwright": None, "browser": None, "context": None, "page": None}
session_vector_db = None
synthesis_queue = queue.Queue()
synthesis_worker_thread = None
system_prompt = _get_env_system_prompt(
    """
You are RIGEL, a helpful assistant developed by Zerone Laboratories.
"""
)

class _Signal:

    def __init__(self):
        self._handlers = []

    def connect(self, handler):
        """Register *handler* (an EmitSignal lambda from pydbus).

        Returns a tiny context manager whose .__exit__ tears down the
        handler, satisfying pydbus's _at_exit cleanup contract.
        """
        self._handlers.append(handler)

        class _Connected:
            def __exit__(self_, *a):
                try:
                    self._handlers.remove(handler)
                except ValueError:
                    pass

        return _Connected()

    def emit(self, *args):
        for h in self._handlers:
            try:
                h(*args)
            except Exception:
                pass

    def __call__(self, *args):
        """Allow self.TranscriptionUpdate(text) sugar — delegates to emit."""
        self.emit(*args)


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
            <method name='RigelNaturalLanguage'>
                <arg type='s' name='query' direction='in'/>
                <arg type='s' name='id' direction='in'/>
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
            <method name='LiveVoiceRecognition'>
                <arg type='s' name='action' direction='in'/>
                <arg type='s' name='config_json' direction='in'/>
                <arg type='s' name='result' direction='out'/>
            </method>
            <signal name='TranscriptionUpdate'>
                <arg type='s' name='text'/>
            </signal>
            <method name='GetLicenseInfo'>
                <arg type='s' name='license_info' direction='out'/>
            </method>
            <method name='AnalyzeImage'>
                <arg type='s' name='image_path' direction='in'/>
                <arg type='s' name='prompt' direction='in'/>
                <arg type='s' name='result' direction='out'/>
            </method>
            <!-- CodingAgent methods (RigelClaude extension) -->
            <method name='CodingAgentGenerateCode'>
                <arg type='s' name='specification' direction='in'/>
                <arg type='s' name='language' direction='in'/>
                <arg type='s' name='code' direction='out'/>
            </method>
            <method name='CodingAgentReviewCode'>
                <arg type='s' name='code' direction='in'/>
                <arg type='s' name='language' direction='in'/>
                <arg type='s' name='review' direction='out'/>
            </method>
            <method name='CodingAgentDebugCode'>
                <arg type='s' name='code' direction='in'/>
                <arg type='s' name='error' direction='in'/>
                <arg type='s' name='language' direction='in'/>
                <arg type='s' name='result' direction='out'/>
            </method>
            <method name='CodingAgentRefactorCode'>
                <arg type='s' name='code' direction='in'/>
                <arg type='s' name='instructions' direction='in'/>
                <arg type='s' name='language' direction='in'/>
                <arg type='s' name='result' direction='out'/>
            </method>
            <method name='CodingAgentExplainCode'>
                <arg type='s' name='code' direction='in'/>
                <arg type='s' name='language' direction='in'/>
                <arg type='s' name='explanation' direction='out'/>
            </method>
            <method name='CodingAgentExecuteCode'>
                <arg type='s' name='file_path' direction='in'/>
                <arg type='s' name='args_json' direction='in'/>
                <arg type='s' name='output' direction='out'/>
            </method>
            <method name='CodingAgentGetStatus'>
                <arg type='s' name='status_json' direction='out'/>
            </method>
            <method name='CodingAgentGetHistory'>
                <arg type='s' name='last_n' direction='in'/>
                <arg type='s' name='history_json' direction='out'/>
            </method>
            <method name='CodingAgentLaunch'>
                <arg type='s' name='result_json' direction='out'/>
            </method>
            <method name='CodingAgentClose'>
                <arg type='s' name='result_json' direction='out'/>
            </method>
            <signal name='CodingAgentStatusUpdate'>
                <arg type='s' name='status_json'/>
            </signal>
        </interface>
    </node>
    """

    TranscriptionUpdate = _Signal()
    CodingAgentStatusUpdate = _Signal()

    def GetLicenseInfo(self):
        """Return license information for AGPL compliance"""
        import json
        license_info = {
            "name": "RIGEL Engine",
            "version": VERSION,
            "license": "GNU Affero General Public License v3.0",
            "source": "https://github.com/Zerone-Laboratories/RIGEL",
            "copyright": "Copyright (C) 2025 Zerone Laboratories",
            "agpl_notice": "This program is free software under AGPL-3.0. If you run a modified version as a network service, you must provide source code to users."
        }
        return json.dumps(license_info, indent=2)

    def Query(self, query, system_prompt_=None):
        global system_prompt, rigel
        if system_prompt_ is not None:
            system_prompt = system_prompt_
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

    # def QueryWithMemory(self, query, id):
    #     # syslog.info(f"QueryWithMemory called with query: {query[:100]}... (tool memory disabled)")
    #     # return self.QueryWithTools(query)
    #     global rigel


    def QueryWithMemory(self, query, id):
        global system_prompt, rigel
        # print(f"DEBUG: {RAG}")
        messages = [
            (
                "system",
                system_prompt
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
        response = rigel.think(query)
        return response



    def RigelNaturalLanguage(self, query, id="default"):

        def has_call_tool_agent(text: str) -> bool:
            pattern = r'\[CALL[\s_\-]*TOOL[\s_\-]*AGENT\s*:\s*.+?\]'
            return bool(re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL))

        syslog.info(f"RigelNaturalLanguage called with query: {query[:100]}...")
        persona_profile = """
        Your personality template is,
        - Direct = 80%
        - helpful = 82%
        - respective = 85%
        - Sarcastic = 73%
        - Humor = 68%
        Your role is a butler for the user. Be formal, but follow the template.
        """
        agent_system_prompt = f"""
           {system_prompt}
           <PERSONA> {persona_profile} </PERSONA>
            You are the memory / decision agent. You do not have tool capabilities yourself.
            Decide what kind of execution the user request needs, if any.

            --- TOOL AGENT ---
            If the request needs command execution, system state checks, file operations,
            app/process management, time/date, network inspection, or web browsing,
            reply exactly:
            [CALL_TOOL_AGENT: <single concise task for tool agent>]

            --- CODING AGENT ---
            If the request involves writing code, generating a project, debugging,
            refactoring, code review, creating files/scripts, building software,
            or any software engineering task, reply exactly:
            [CALL_CODING_AGENT: <detailed task for the coding agent>]
            The coding agent runs in the BACKGROUND. When you activate it, immediately
            inform the user that the coding agent has started and they can check its
            status by asking. DO NOT wait for the coding agent to finish.

            --- STATUS CHECK ---
            If the user asks about the coding agent's progress or status, reply:
            [CODING_AGENT_STATUS_CHECK]
            You will receive the status and report it to the user.

            If no tools or agents are needed, answer directly.
            Response style:
            Use only natural language.
            IMPORT PERSONALITY PROFILE
            LIST OUTPUT = False
            TUTORIALS = False
            MARKDOWN = False
            NUMBERS = False
            TEXT = True
            NaturalLanguage = True
            CONVERT NUMBERS->TEXT

            Keep it short and concise whenever possible.
        """
        messages = [
            ("system", agent_system_prompt),
            ("human", f"{query}")
        ]
        response = rigel.inference_with_memory(messages=messages, thread_id=id)
        decision_text = response.content if hasattr(response, "content") else str(response)
        decision_text = decision_text.strip()
        syslog.info(f"Memory decision text: {decision_text}")

        output = "[CONTEXT: NULL]"
        while True:
            if self._has_coding_agent_status_check(decision_text):
                syslog.info("CODING_AGENT_STATUS_CHECK pattern detected")
                status_text = self._get_coding_agent_status_text()
                messages = [
                    ("system", agent_system_prompt),
                    ("human", f"Coding agent status: {status_text}\n\nUser original request: {query}. Report this status to the user in natural language.")
                ]
                response = rigel.inference_with_memory(messages=messages, thread_id=id)
                decision_text = response.content if hasattr(response, "content") else str(response)
                break

            if self._has_call_coding_agent(decision_text):
                syslog.info("CALL_CODING_AGENT pattern detected, spawning background task")
                self.SynthesizeText(f"Establishing Connection with RIGEL ClaudeCode Integration")
                coding_task = self._extract_coding_agent_task(decision_text)
                if coding_task:
                    self._spawn_background_coding_task(coding_task)
                    output = (
                        f"<CODING-AGENT-OUTPUT: Background coding task started. "
                        f"Task: '{coding_task}'. The coding agent is now working. "
                        f"Inform the user it has begun and they can ask for status updates.>"
                    )
                else:
                    syslog.warning("CALL_CODING_AGENT pattern detected but failed to extract task")
                    output = "<CODING-AGENT-OUTPUT: Failed to extract the coding task. Notify User.>"
                messages = [
                    ("system", agent_system_prompt),
                    ("human", f"Coding agent result: {output}\n\nUser original request: {query}. Inform the user the coding agent has started working in the background.")
                ]
                response = rigel.inference_with_memory(messages=messages, thread_id=id)
                if self._has_call_coding_agent(response.content if hasattr(response, "content") else str(response)):
                    syslog.warning("Second CALL_CODING_AGENT detected, re-triggering")
                    decision_text = response.content if hasattr(response, "content") else str(response)
                    continue
                else:
                    break

            if has_call_tool_agent(decision_text):
                syslog.info("CALL_TOOL_AGENT pattern detected, delegating to QueryWithTools")
                self.SynthesizeText(f"Establishing Connection with RIGEL Model Context Protocol")
                tool_task = self._extract_tool_agent_task(decision_text)
                if tool_task:
                    output = f"""<TOOL-AGENT-OUTPUT: {self.QueryWithTools(tool_task)}>"""
                else:
                    syslog.warning("CALL_TOOL_AGENT pattern detected but failed to extract task")
                    output = "<TOOL-AGENT-OUTPUT: Failure while extracting the prompt. Notify User>"
                messages = [
                    ("system", agent_system_prompt),
                    ("human", f"Output of the tool agent execution for the task '{tool_task}': {output}\n\nUser original request: {query}. Inform the user of the tool agent output and provide a final response.")
                ]
                response = rigel.inference_with_memory(messages=messages, thread_id=id)
                decision_text = (response.content if hasattr(response, "content") else str(response)).strip()
                # Re-evaluate all directives, not just tool calls.
                if (
                    self._has_coding_agent_status_check(decision_text)
                    or self._has_call_coding_agent(decision_text)
                    or has_call_tool_agent(decision_text)
                ):
                    continue
                break

            else:
                syslog.info("No agent call pattern detected, returning response directly")
                response = decision_text
                break

        return response.content if hasattr(response, "content") else str(response)


    # LEGACY RIGEL NATURAL LANGUAGE MULTI-AGENT SYSTEM
    # def RigelNaturalLanguage(self, query, id="default"):
    #     global rigel, system_prompt

    #     if rigel is None:
    #         syslog.error("RigelNaturalLanguage called before rigel backend initialization")
    #         return "Error: RIGEL backend not initialized"

    #     thread_id = id or "default"
    #     syslog.info(f"RigelNaturalLanguage called with query: {query[:100]}... thread: {thread_id}")

    #     try:
    #         session_context = self._get_vector_session_context(thread_id, query)
    #         syslog.info(f"Retrieved session context length: {len(session_context) if session_context else 0} for thread {thread_id}")
    #         user_input_with_context = query

    #         summerized_session_context = self.Query(
    #             system_prompt_=f"""
    #             You are a context summarization agent for RIGEL's natural language reasoning flow.
    #             Summarize the following session context.
    #             """,
    #             query=user_input_with_context,
    #         )
    #         syslog.info(f"Context summarization completed. Summary length: {len(summerized_session_context) if summerized_session_context else 0}")

    #         if session_context:
    #             user_input_with_context = (
    #                 f"Relevant session memory context:\n{summerized_session_context}\n\n"
    #                 f"Current user request:\n{query}"
    #             )
    #             syslog.info("Built user input with summarized session context for memory agent prompt")
    #         else:
    #             syslog.info("No session context available; using raw query for memory agent prompt")

    #         memory_agent_prompt = f"""
    #         {system_prompt}

    #         You are the memory agent.
    #         You do not have tool capabilities.

    #         Decide if the user request needs tool execution.
    #         If tools are required, reply exactly like this:
    #         CALL_TOOL_AGENT: <single concise task for tool agent>
    #         Tool agent has following capabilities:
    #         - Command execution
    #         - System state checks
    #         - File operations
    #         - App and process management
    #         - Current time and date retrieval
    #         - Network and environment inspection
    #         - All operating system related tasks should be delegated to the tool agent

    #         If tools are not required, answer directly.

    #         Response style:
    #         Use only natural language.
    #         Keep it short and concise whenever possible.
    #         No lists.
    #         No tutorials.
    #         No markdown.
    #         """
    #         syslog.info("Constructed memory agent prompt")

    #         memory_decision = rigel.inference_with_memory(
    #             messages=[
    #                 ("system", memory_agent_prompt),
    #                 ("human", user_input_with_context),
    #             ],
    #             thread_id=thread_id,
    #             RAG=False,
    #         )
    #         syslog.info("Memory agent inference completed")

    #         decision_text = memory_decision.content if hasattr(memory_decision, "content") else str(memory_decision)
    #         decision_text = decision_text.strip()
    #         syslog.info(f"Memory decision text: {decision_text[:200]}")

    #         delegated = False
    #         tool_task = self._resolve_tool_task(decision_text, query, thread_id)
    #         syslog.info(f"Resolved tool task: {tool_task if tool_task else 'none'}")

    #         output = decision_text
    #         max_tool_rounds = int(os.getenv("NATURAL_LANGUAGE_MAX_TOOL_ROUNDS", "3"))
    #         round_count = 0

    #         while tool_task is not None and round_count < max_tool_rounds:
    #             delegated = True
    #             round_count += 1
    #             syslog.info(f"Starting tool round {round_count} with task: {tool_task}")
    #             tool_task = tool_task or query
    #             tool_output_text = self._execute_nl_tool_task(tool_task, thread_id)
    #             syslog.info(f"Tool round {round_count} completed. Output length: {len(tool_output_text) if tool_output_text else 0}")

    #             post_tool_prompt = f"""
    #             {system_prompt}

    #             You are the memory agent.
    #             You do not have tool capabilities.
    #             You now received tool output.

    #             If another tool call is still required, reply exactly:
    #             '</ CALL_TOOL_AGENT: <single concise follow-up task>>'

    #             If no further tool call is needed, provide the final response naturally.

    #             Response style:
    #             Use only natural language.
    #             Keep it short and concise whenever possible.
    #             No lists.
    #             No tutorials.
    #             No markdown.
    #             """
    #             syslog.info(f"Constructed post-tool prompt for round {round_count}")

    #             post_tool_decision = rigel.inference_with_memory(
    #                 messages=[
    #                     ("system", post_tool_prompt),
    #                     (
    #                         "human",
    #                         f"User request: {query}\nSession context: {session_context}\nTool output round {round_count}: {tool_output_text}",
    #                     ),
    #                 ],
    #                 thread_id=thread_id,
    #                 RAG=False,
    #             )
    #             syslog.info(f"Post-tool inference completed for round {round_count}")

    #             output = post_tool_decision.content if hasattr(post_tool_decision, "content") else str(post_tool_decision)
    #             output = output.strip()
    #             syslog.info(f"Post-tool output: {output[:200]}")
    #             tool_task = self._resolve_tool_task(output, query, thread_id)
    #             syslog.info(f"Resolved follow-up tool task: {tool_task if tool_task else 'none'}")

    #         if (not delegated) and self._looks_like_capability_refusal(output):
    #             syslog.info("RigelNaturalLanguage fallback: capability refusal detected, retrying with tool agent")
    #             tool_output_text = self._execute_nl_tool_task(query, thread_id)
    #             syslog.info(f"Fallback tool execution completed. Output length: {len(tool_output_text) if tool_output_text else 0}")

    #             summarize_prompt = f"""
    #             {system_prompt}

    #             You are the memory agent.
    #             The tool agent has completed execution.
    #             Summarize the result naturally for the user.

    #             Response style:
    #             Use only natural language.
    #             Keep it short and concise whenever possible.
    #             No lists.
    #             No tutorials.
    #             No markdown.
    #             """
    #             syslog.info("Constructed summarize prompt for fallback")

    #             summarized = rigel.inference_with_memory(
    #                 messages=[
    #                     ("system", summarize_prompt),
    #                     ("human", f"User request: {query}\nSession context: {session_context}\nTool output: {tool_output_text}"),
    #                 ],
    #                 thread_id=thread_id,
    #                 RAG=False,
    #             )
    #             output = summarized.content if hasattr(summarized, "content") else str(summarized)
    #             syslog.info(f"Fallback summary output: {output[:200]}")

    #         final_output = self._sanitize_natural_language_output(output)
    #         syslog.info(f"Sanitized final output: {final_output[:200]}")
    #         self._save_vector_session_turn(thread_id, query, final_output)
    #         syslog.info("Saved vector session turn successfully")

    #         return final_output
    #     except Exception as e:
    #         error_msg = f"Error in RigelNaturalLanguage: {str(e)}"
    #         syslog.error(error_msg)
    #         return f"Error: {error_msg}"

    def QueryWithTools(self, query):
        tool_engine = os.getenv("TOOL_CALL_ENGINE", "ollama").lower()
        default_tool_model = "qwen3:0.6b" if tool_engine == "ollama" else os.getenv("TOOL_CALL_GROQ_MODEL", "qwen/qwen3-32b")
        tool_model = os.getenv("TOOL_CALL_MODEL", default_tool_model)
        tool_temp = float(os.getenv("TOOL_TEMPERATURE", os.getenv("TEMPERATURE", "0.0")))

        tool_mcp = globals().get("default_mcp")
        if tool_mcp is None:
            tools_sse_url = get_tools_sse_url()
            tool_mcp = MultiServerMCPClient(
                {
                    "rigel tools": {
                        "url": tools_sse_url,
                        "transport": "sse",
                    },
                },
            )

        rigel_agent = (
            RigelGroq(model_name=tool_model, temp=tool_temp, mcp_endpoint=tool_mcp)
            if tool_engine == "groq"
            else RigelOllama(model_name=tool_model, mcp_endpoint=tool_mcp)
        )

        syslog.info(f"QueryWithTools called with query: {query}...")
        print(f"\n\n\n\nTOOL CALL QUERY {query}\n\n\n\n")
        thread_id = f"tools-{uuid.uuid4()}"
        try:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(self._run_async_tools_query, query, rigel_agent, thread_id)
                result = future.result(timeout=120)

            return str(result)

        except concurrent.futures.TimeoutError:
            error_msg = "Query with tools timed out after 2 minutes"
            syslog.error(error_msg)
            return f"Error: {error_msg}"
        except Exception as e:
            error_msg = f"Error occurred during tool-based inference: {str(e)}"
            syslog.error(error_msg)
            return f"Error: {error_msg}"
        finally:
            try:
                rigel_agent.clear_tools_memory(thread_id)
            except Exception as cleanup_error:
                syslog.warning(f"Failed to clear tool memory for thread {thread_id}: {cleanup_error}")

    def _run_async_tools_query(self, query, rigel, thread_id):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(rigel.inference_with_tools_and_memory(query, thread_id=thread_id))
        finally:
            loop.close()

    def _sanitize_natural_language_output(self, text):
        if not text:
            return ""

        cleaned = re.sub(r"<\s*think\s*>.*?<\s*/\s*think\s*>", " ", text, flags=re.IGNORECASE | re.DOTALL)
        cleaned = re.sub(r"\bthink\b.*?\s/think\b", " ", cleaned, flags=re.IGNORECASE | re.DOTALL)
        cleaned = re.sub(r"^\s*CALL[\s_\-]*TOOL[\s_\-]*AGENT\s*:\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = cleaned.replace("\n", " ")
        cleaned = re.sub(r"[*_`~#<>\[\]{}|\\]", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    def _normalize_home_paths(self, text: str) -> str:
        """Normalize ~ paths to an absolute host home path for downstream execution."""
        if not text:
            return text
        preferred_home = os.getenv("HOST_HOME", "/home/zerone").rstrip("/")
        return re.sub(r"(?<![A-Za-z0-9_])~(?=/|$)", preferred_home, text)

    def _extract_tool_agent_task(self, decision_text):
        if not decision_text:
            return None

        match = re.search(
            r"\[CALL[\s_\-]*TOOL[\s_\-]*AGENT\s*:\s*(.*?)\]",
            decision_text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not match:
            return None
        task = match.group(1).strip()
        return self._normalize_home_paths(task)

    def _resolve_tool_task(self, decision_text, user_query, thread_id):
        tool_task = self._extract_tool_agent_task(decision_text)
        if tool_task is not None:
            return tool_task or user_query

        return None

    # Coding agent helpers ---

    def _has_call_coding_agent(self, text: str) -> bool:
        return self._extract_coding_agent_task(text or "") is not None

    def _has_coding_agent_status_check(self, text: str) -> bool:
        pattern = r'\[CODING[\s_\-]*AGENT[\s_\-]*STATUS[\s_\-]*CHECK\]'
        return bool(re.search(pattern, text, flags=re.IGNORECASE))

    def _extract_coding_agent_task(self, decision_text: str) -> Optional[str]:
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
                return self._normalize_home_paths(task) if task else None
        return None

    def _get_coding_agent_status_text(self) -> str:
        global _coding_agent_background_task

        agent = self._get_coding_agent()
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

    def _spawn_background_coding_task(self, task: str):
        global _coding_agent_background_task

        agent = self._get_coding_agent()
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

        def _run_and_broadcast():
            try:
                result = agent.coding_task(task)
                task_record["result_preview"] = (result or "")[:300]
            except Exception as e:
                task_record["error"] = str(e)
                syslog.error(f"Background coding task error: {e}")
            finally:
                task_record["end_time"] = datetime.now().isoformat()
                try:
                    self._broadcast_coding_agent_status()
                except Exception:
                    pass

        thread = threading.Thread(target=_run_and_broadcast, daemon=True)
        task_record["thread"] = thread
        thread.start()

        self._broadcast_coding_agent_status()
        syslog.info(f"Coding agent started background task: {task[:100]}...")


    def _looks_like_capability_refusal(self, text):
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

    def _get_vector_db(self):
        global session_vector_db
        if session_vector_db is None:
            try:
                session_vector_db = DBConn()
            except Exception as e:
                syslog.warning(f"Vector DB unavailable: {str(e)}")
                session_vector_db = False
        return session_vector_db if session_vector_db is not False else None

    def _get_vector_session_context(self, session_id, query):
        db = self._get_vector_db()
        if db is None:
            return ""
        try:
            return db.search_session_context(session_id=session_id, query=query, n_results=4)
        except Exception as e:
            syslog.warning(f"Failed to retrieve vector session context: {str(e)}")
            return ""

    def _save_vector_session_turn(self, session_id, user_text, assistant_text):
        db = self._get_vector_db()
        if db is None:
            return
        try:
            db.save_session_turn(
                session_id=session_id,
                user_text=user_text,
                assistant_text=assistant_text,
                source="dbus-rigel-natural-language",
            )
        except Exception as e:
            syslog.warning(f"Failed to save vector session turn: {str(e)}")

    def _execute_nl_tool_task(self, tool_task, thread_id):
        return self.QueryWithTools(tool_task)

    def SynthesizeText(self, text, mode="chunk"):
        try:
            syslog.info(f"SynthesizeText called with mode: {mode}, text length: {len(text)}")

            _ensure_synthesis_worker_running()
            request = {
                "text": text,
                "mode": mode,
            }
            synthesis_queue.put(request)
            queue_position = synthesis_queue.qsize()
            return (
                f"Text synthesis queued successfully with mode: {mode}. "
                f"Position in queue: {queue_position}"
            )

        except Exception as e:
            error_msg = f"Error queueing text synthesis: {str(e)}"
            syslog.error(error_msg)
            return error_msg

    def RecognizeAudio(self, audio_file_path, model="small"):
        global recognizer

        try:
            syslog.info(f"RecognizeAudio called with file: {audio_file_path}, model: {model}")
            resolved_audio_file_path = audio_file_path
            if not os.path.exists(resolved_audio_file_path):
                host_tmp_mount = os.environ.get("HOST_TMP_MOUNT", "/host_tmp")
                if audio_file_path.startswith("/tmp/") and os.path.isdir(host_tmp_mount):
                    remapped_path = os.path.join(host_tmp_mount, os.path.relpath(audio_file_path, "/tmp"))
                    if os.path.exists(remapped_path):
                        resolved_audio_file_path = remapped_path
                        syslog.info(
                            f"Resolved host tmp audio path from {audio_file_path} to {resolved_audio_file_path}"
                        )

            if not os.path.exists(resolved_audio_file_path):
                return (
                    f"Error: Audio file not found: {audio_file_path}. "
                    "If this file is created on the host, mount host /tmp into the container "
                    "(for example: /tmp:/host_tmp) and set HOST_TMP_MOUNT accordingly."
                )
            if recognizer is None:
                recognizer = Recognizer(model=model)
            elif hasattr(recognizer, 'model_name') and recognizer.model_name != model:
                recognizer = Recognizer(model=model)
            transcription = recognizer.transcribe(resolved_audio_file_path)
            syslog.info(f"Transcription completed: {transcription[:100]}...")

            return transcription

        except Exception as e:
            error_msg = f"Error in audio recognition: {str(e)}"
            syslog.error(error_msg)
            return error_msg

    def LiveVoiceRecognition(self, action, config_json="{}"):
        """Start/stop live voice recognition using whisper-stream.

        Streaming via DBus signals:
          - Call start → method returns immediately, transcription lines are
            emitted as TranscriptionUpdate(text) signals in real time.
          - Subscribe to the com.rigel.RigelService.TranscriptionUpdate signal
            to receive transcription lines as they are captured.

        action: 'start' | 'stop' | 'status' | 'transcribe_file'
        config_json: JSON string with configuration, e.g.:
            {"model": "tiny.en", "capture_device": -1, "threads": 8, "step": 500, "length": 5000}
            or for transcribe_file: {"model": "tiny.en", "file_path": "/path/to/audio.wav"}
        """
        global live_recognizer

        try:
            config = json.loads(config_json) if config_json else {}
        except json.JSONDecodeError:
            return json.dumps({"status": "error", "message": "Invalid config_json"})

        model = config.get("model") or os.getenv("LIVE_VOICE_RECOGNITION_MODEL", "tiny.en")

        try:
            if action == "start":
                if live_recognizer is not None and live_recognizer.is_capturing():
                    return json.dumps({"status": "error", "message": "Live recognition already running"})

                capture_device = config.get("capture_device", -1)
                threads = config.get("threads", 8)
                step = config.get("step", 500)
                length = config.get("length", 5000)

                live_recognizer = LiveVoiceRecognizer(
                    model=model,
                    capture_device=capture_device,
                    threads=threads,
                    step=step,
                    length=length,
                )

                def on_line(line):
                    """Called for each transcription line from whisper-stream.
                    Emits the text as a DBus TranscriptionUpdate signal so
                    clients receive it in real time."""
                    syslog.info(f"LiveVoiceRecognition: {line}")
                    try:
                        self.TranscriptionUpdate.emit(line)
                    except Exception as exc:
                        syslog.error(f"Failed to emit TranscriptionUpdate signal: {exc}")

                live_recognizer.start_device_capture(callback=on_line)
                syslog.info(f"LiveVoiceRecognition started with model={model}, device={capture_device}")
                return json.dumps({
                    "status": "started",
                    "model": model,
                    "capture_device": capture_device,
                })

            elif action == "stop":
                if live_recognizer is None:
                    return json.dumps({"status": "error", "message": "No live recognition running"})

                live_recognizer.stop_device_capture()
                result = json.dumps({"status": "stopped"})
                live_recognizer = None
                return result

            elif action == "status":
                if live_recognizer is None:
                    return json.dumps({"status": "idle"})
                running = live_recognizer.is_capturing()
                return json.dumps({"status": "capturing" if running else "idle"})

            elif action == "transcribe_file":
                file_path = config.get("file_path")
                if not file_path:
                    return json.dumps({"status": "error", "message": "file_path required in config_json"})

                lvr = LiveVoiceRecognizer(model=model)
                transcription = lvr.transcribe_file(file_path)
                return json.dumps({"status": "completed", "transcription": transcription})

            else:
                return json.dumps({"status": "error", "message": f"Unknown action: {action}"})

        except FileNotFoundError as e:
            return json.dumps({"status": "error", "message": f"Binary/model not found: {str(e)}"})
        except Exception as e:
            error_msg = f"Error in live voice recognition: {str(e)}"
            syslog.error(error_msg)
            return json.dumps({"status": "error", "message": error_msg})

    def AnalyzeImage(self, image_path, prompt):
        global vision_engine

        try:
            syslog.info(f"AnalyzeImage called with path: {image_path}")

            if not os.path.exists(image_path):
                return json.dumps({"error": f"Image file not found: {image_path}"})

            if vision_engine is None:
                vision_engine = get_vision_engine()

            result = vision_engine.analyze_image(image_path, prompt)
            return json.dumps(result, indent=2)

        except Exception as e:
            error_msg = f"Error in image analysis: {str(e)}"
            syslog.error(error_msg)
            return json.dumps({"error": error_msg})

    # ------------------------------------------------------------------
    # CodingAgent methods (RigelClaude extension)
    # ------------------------------------------------------------------

    def _get_coding_agent(self):
        global _coding_agent
        if not _RIGEL_CLAUDE_ENABLED:
            return None
        if _coding_agent is None:
            syslog.info("Creating RigelClaude coding agent (lazy init)")
            _coding_agent = RigelClaude(auto_launch=False)
        return _coding_agent

    def _broadcast_coding_agent_status(self):
        agent = self._get_coding_agent()
        if agent is None:
            return
        try:
            status = agent.get_status()
            self.CodingAgentStatusUpdate(json.dumps(status))
        except Exception as e:
            syslog.warning(f"Failed to broadcast CodingAgent status: {e}")

    def CodingAgentGenerateCode(self, specification, language="python"):
        agent = self._get_coding_agent()
        if agent is None:
            return json.dumps({"error": "RigelClaude is not enabled. Set RIGEL_CLAUDE_ENABLED=true in .env"})
        try:
            result = agent.generate_code(specification, language)
            self._broadcast_coding_agent_status()
            return result
        except Exception as e:
            return json.dumps({"error": str(e)})

    def CodingAgentReviewCode(self, code, language="python"):
        agent = self._get_coding_agent()
        if agent is None:
            return json.dumps({"error": "RigelClaude is not enabled. Set RIGEL_CLAUDE_ENABLED=true in .env"})
        try:
            result = agent.review_code(code, language)
            self._broadcast_coding_agent_status()
            return result
        except Exception as e:
            return json.dumps({"error": str(e)})

    def CodingAgentDebugCode(self, code, error, language="python"):
        agent = self._get_coding_agent()
        if agent is None:
            return json.dumps({"error": "RigelClaude is not enabled. Set RIGEL_CLAUDE_ENABLED=true in .env"})
        try:
            result = agent.debug_code(code, error, language)
            self._broadcast_coding_agent_status()
            return result
        except Exception as e:
            return json.dumps({"error": str(e)})

    def CodingAgentRefactorCode(self, code, instructions, language="python"):
        agent = self._get_coding_agent()
        if agent is None:
            return json.dumps({"error": "RigelClaude is not enabled. Set RIGEL_CLAUDE_ENABLED=true in .env"})
        try:
            result = agent.refactor_code(code, instructions, language)
            self._broadcast_coding_agent_status()
            return result
        except Exception as e:
            return json.dumps({"error": str(e)})

    def CodingAgentExplainCode(self, code, language="python"):
        agent = self._get_coding_agent()
        if agent is None:
            return json.dumps({"error": "RigelClaude is not enabled. Set RIGEL_CLAUDE_ENABLED=true in .env"})
        try:
            result = agent.explain_code(code, language)
            self._broadcast_coding_agent_status()
            return result
        except Exception as e:
            return json.dumps({"error": str(e)})

    def CodingAgentExecuteCode(self, file_path, args_json="[]"):
        agent = self._get_coding_agent()
        if agent is None:
            return json.dumps({"error": "RigelClaude is not enabled. Set RIGEL_CLAUDE_ENABLED=true in .env"})
        try:
            args = json.loads(args_json) if args_json else None
            result = agent.execute_code_in_project(file_path, args)
            self._broadcast_coding_agent_status()
            return result
        except Exception as e:
            return json.dumps({"error": str(e)})

    def CodingAgentGetStatus(self):
        agent = self._get_coding_agent()
        if agent is None:
            return json.dumps({"error": "RigelClaude is not enabled. Set RIGEL_CLAUDE_ENABLED=true in .env"})
        try:
            status = agent.get_status()
            return json.dumps(status)
        except Exception as e:
            return json.dumps({"error": str(e)})

    def CodingAgentGetHistory(self, last_n="20"):
        agent = self._get_coding_agent()
        if agent is None:
            return json.dumps({"error": "RigelClaude is not enabled. Set RIGEL_CLAUDE_ENABLED=true in .env"})
        try:
            history = agent.get_coding_history(last_n=int(last_n))
            return json.dumps(history)
        except Exception as e:
            return json.dumps({"error": str(e)})

    def CodingAgentLaunch(self):
        agent = self._get_coding_agent()
        if agent is None:
            return json.dumps({"error": "RigelClaude is not enabled. Set RIGEL_CLAUDE_ENABLED=true in .env"})
        try:
            result = agent.launch()
            self._broadcast_coding_agent_status()
            return json.dumps(result)
        except Exception as e:
            return json.dumps({"error": str(e)})

    def CodingAgentClose(self):
        agent = self._get_coding_agent()
        if agent is None:
            return json.dumps({"error": "RigelClaude is not enabled. Set RIGEL_CLAUDE_ENABLED=true in .env"})
        try:
            result = agent.close()
            self._broadcast_coding_agent_status()
            return json.dumps(result)
        except Exception as e:
            return json.dumps({"error": str(e)})


if __name__ == "__main__":
    print("RIGEL DBUS Interface")
    print("Copyright (C) 2025 Zerone Laboratories")
    print("Licensed under GNU Affero General Public License v3.0")
    print("This is free software; see the source for copying conditions.")
    print("")
    default_mcp = None
    tools_sse_url = get_tools_sse_url()
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

    inference_engine = os.environ.get("NORMAL_CHAT_ENGINE", os.environ.get("INFERENCE_ENGINE", "groq")).lower()
    general_model = os.getenv("NORMAL_CHAT_MODEL") or os.getenv("GENERAL_LLM_MODEL")
    if inference_engine == "groq":
        model_to_use = general_model or os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
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

    # Initialize live voice recognition components
    print("Initializing live voice recognition...")
    try:
        live_recognizer = LiveVoiceRecognizer(
            model=os.getenv("LIVE_VOICE_RECOGNITION_MODEL", "tiny.en")
        )
        print("Live voice recognition initialized successfully")
    except Exception as e:
        print(f"Warning: Failed to initialize live voice recognition: {e}")
        print("Live voice recognition features may not be available")

    # Initialize vision components
    print("Initializing vision engine...")
    try:
        vision_engine = get_vision_engine()
        print(f"Vision engine initialized with backend: {vision_engine.backend}, model: {vision_engine.model}")
    except Exception as e:
        print(f"Warning: Failed to initialize vision engine: {e}")
        print("Vision features may not be available")

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
    print("  - RigelNaturalLanguage: Memory first multi agent natural language flow")
    print("  - SynthesizeText: Convert text to speech with specified mode")
    print("  - RecognizeAudio: Transcribe audio file to text")
    print("  - LiveVoiceRecognition: Start/stop/status live voice recognition with whisper-stream")
    print("     Signal: TranscriptionUpdate(text) - streaming transcription lines")
    print("  - AnalyzeImage: Analyze image with custom prompt")
    print("  - DescribeImage: Get detailed image description")
    print("  - ExtractTextFromImage: OCR - extract text from image")
    print("  - AnalyzeScreenshot: Analyze UI screenshot for elements/actions")
    print("  - FindElementInImage: Find specific UI element by description")
    print("  - BrowserLaunch: Launch browser for automation")
    print("  - BrowserNavigate: Navigate to URL")
    print("  - BrowserScreenshot: Take screenshot")
    print("  - BrowserClick: Click element by selector or text")
    print("  - BrowserType: Type text into input")
    print("  - BrowserScroll: Scroll page")
    print("  - BrowserGetContent: Get page content")
    print("  - BrowserClose: Close browser")
    print("  - GetLicenseInfo: Display license and copyright information")
    print("Press Ctrl+C to stop")

    loop = GLib.MainLoop()
    try:
        loop.run()
    except KeyboardInterrupt:
        print("\nStopping RIGEL D-Bus service...")
        loop.quit()
