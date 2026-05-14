# This file is part of RIGEL Engine.
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

# RigelClaude — Claude Code Wrapper Extension
# Inherits from Rigel, wraps the Claude Code CLI as its inference backend.

from core.rigel import Rigel, default_mcp
from core.logger import SysLog
from langchain_core.messages import AIMessage, SystemMessage
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.checkpoint.memory import MemorySaver
import os
import re
import json
import time
import subprocess
import atexit
import shutil
import threading
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Optional pexpect import — required for interactive Claude Code sessions
# ---------------------------------------------------------------------------
try:
    import pexpect
    PEXPECT_AVAILABLE = True
except ImportError:
    pexpect = None  # type: ignore
    PEXPECT_AVAILABLE = False

syslog = SysLog(name="RigelClaude", level="DEBUG", log_file="rigel_claude.log")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_claude_binary() -> Optional[str]:
    """Locate the Claude Code CLI binary on PATH."""
    return shutil.which("claude")


CLAUDE_BIN = _find_claude_binary()

# Coding-task keywords used for smart routing in inference_with_tools.
CODING_TRIGGERS = [
    "generate code", "write code", "create function", "implement",
    "debug", "fix bug", "fix the bug", "review code", "refactor",
    "explain code", "create file", "write script", "build",
    "write a program", "code the", "program that",
    "```", "def ", "class ", "function(",
    "npm ", "pip ", "docker", "git ",
]


# ---------------------------------------------------------------------------
# RigelClaude
# ---------------------------------------------------------------------------

class RigelClaude(Rigel):

    def __init__(
        self,
        claude_model: Optional[str] = None,
        working_dir: Optional[str] = None,
        log_dir: Optional[str] = None,
        mcp_endpoint=default_mcp,
        auto_launch: bool = True,
    ):
        model_label = claude_model or os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
        super().__init__(
            model_name=model_label,
            chatmode="claude_code",
            mcp_endpoint=mcp_endpoint,
        )

        # Claude Code configuration
        self.claude_model = model_label
        self.working_dir = working_dir or os.getcwd()
        self.log_dir = log_dir or os.path.join(os.getcwd(), "Logs", "rigel_claude")
        Path(self.log_dir).mkdir(parents=True, exist_ok=True)

        # Interactive subprocess state
        self._child: Optional["pexpect.spawn"] = None
        self._status = "uninitialized"  # uninitialized | ready | busy | error | dead
        self._last_output = ""
        self._last_active: Optional[str] = None
        self._launched_at: Optional[str] = None
        self._coding_log: List[Dict[str, str]] = []
        self._startup_output = ""
        self._max_retries = 3
        self._retry_count = 0
        self._active_proc: Optional[subprocess.Popen] = None
        self._active_proc_lock = threading.Lock()
        self._cancel_requested = False

        # Warn if binary is missing
        if CLAUDE_BIN is None:
            syslog.warning(
                "Claude Code CLI ('claude') not found on PATH. "
                "Inference methods will return errors."
            )
        elif not PEXPECT_AVAILABLE:
            syslog.warning(
                "pexpect not available — interactive Claude Code session disabled. "
                "Using 'claude -p' for inference only."
            )

        # Auto-launch interactive session
        if auto_launch and CLAUDE_BIN and PEXPECT_AVAILABLE:
            self._launch_claude_code()
        elif auto_launch and CLAUDE_BIN and not PEXPECT_AVAILABLE:
            syslog.info("Skipping interactive launch (pexpect missing).")

        atexit.register(self._safe_kill)

    def __del__(self):
        self._safe_kill()

    @staticmethod
    def _strip_ansi(text: str) -> str:
        ansi_escape = re.compile(r'\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~]|\][^\x07]*\x07)')
        return ansi_escape.sub('', text)

    @classmethod
    def _clean_output(cls, text: str) -> str:
        text = cls._strip_ansi(text)
        text = text.replace('\r\r\n', '\n').replace('\r\n', '\n').replace('\r', '\n')
        lines = [line for line in text.splitlines() if line.strip()]
        return '\n'.join(lines)


    def _messages_to_prompt(self, messages: list) -> str:
        parts: List[str] = []
        for msg in messages:
            if isinstance(msg, (tuple, list)) and len(msg) == 2:
                role, content = msg
                if role == "system":
                    parts.append(f"System: {content}")
                else:
                    parts.append(str(content))
            elif isinstance(msg, dict):
                role = msg.get("role", "")
                content = msg.get("content", "")
                if role == "system":
                    parts.append(f"System: {content}")
                else:
                    parts.append(str(content))
            elif hasattr(msg, 'type') and hasattr(msg, 'content'):
                if msg.type == "system":
                    parts.append(f"System: {msg.content}")
                else:
                    parts.append(str(msg.content))
            elif hasattr(msg, 'content'):
                parts.append(str(msg.content))
            else:
                parts.append(str(msg))
        return '\n\n'.join(parts)

    def _call_claude_print(self, prompt: str, allowed_tools: Optional[str] = None,
                        add_dir: Optional[str] = None) -> str:
        if CLAUDE_BIN is None:
            return "[RigelClaude Error: Claude Code CLI ('claude') not found on PATH.]"

        cmd = [CLAUDE_BIN, "-p"]
        if allowed_tools:
            cmd += ["--allowedTools", allowed_tools]
        if add_dir:
            cmd += ["--add-dir", add_dir]
        # Do NOT append prompt as positional arg — pass via stdin instead

        try:
            syslog.info(f"Running: claude -p via stdin (cwd={self.working_dir})")
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=self.working_dir,
                env={**os.environ},
            )
            with self._active_proc_lock:
                self._active_proc = proc
                self._cancel_requested = False
            output, stderr = proc.communicate(input=prompt, timeout=600)
            output = (output or "").strip()
            err = (stderr or "").strip()
            returncode = proc.returncode
            with self._active_proc_lock:
                if self._active_proc is proc:
                    self._active_proc = None

            if returncode != 0:
                if self._cancel_requested:
                    self._cancel_requested = False
                    syslog.info("claude -p task was cancelled by user request")
                    return "[RigelClaude Error: Claude Code task was cancelled.]"
                syslog.error(f"claude -p exited {returncode}: {err or 'unknown error'}")
                if not output:
                    return f"[RigelClaude Error: Claude Code exited {returncode}: {err or 'unknown error'}]"
            cleaned = self._clean_output(output)
            syslog.info(f"claude -p returned {len(cleaned)} chars")
            return cleaned if cleaned else output
        except subprocess.TimeoutExpired:
            with self._active_proc_lock:
                proc_ref = self._active_proc
            if proc_ref is not None:
                try:
                    proc_ref.kill()
                except Exception:
                    pass
                try:
                    proc_ref.communicate(timeout=2)
                except Exception:
                    pass
            with self._active_proc_lock:
                self._active_proc = None
            return "[RigelClaude Error: Claude Code timed out after 600s.]"
        except FileNotFoundError:
            with self._active_proc_lock:
                self._active_proc = None
            return "[RigelClaude Error: Claude Code CLI ('claude') not found on PATH.]"
        except Exception as e:
            with self._active_proc_lock:
                self._active_proc = None
            syslog.error(f"_call_claude_print failed: {e}")
            return f"[RigelClaude Error: {e}]"
        
    def _read_output(self, timeout: float = 2.0) -> str:
        if self._child is None or not self._child.isalive():
            return ""
        chunks: List[str] = []
        while True:
            try:
                chunk = self._child.read_nonblocking(size=10000, timeout=timeout)
                chunks.append(chunk)
            except (pexpect.TIMEOUT, pexpect.EOF):
                break
        return ''.join(chunks)

    def _append_coding_log(self, role: str, message: str) -> None:
        entry = {
            "timestamp": datetime.now().isoformat(),
            "role": role,
            "message": message,
        }
        self._coding_log.append(entry)
        try:
            log_path = os.path.join(
                self.log_dir,
                f"coding_session_{datetime.now().strftime('%Y%m%d')}.log",
            )
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry) + '\n')
        except Exception as e:
            syslog.warning(f"Failed to write coding log: {e}")

    def _launch_claude_code(self) -> Dict[str, Any]:
        """
        Spawn an interactive Claude Code subprocess via pexpect.

        Adapted from the deprecated ``launch_agent`` MCP tool.
        """
        if self._child is not None and self._child.isalive():
            return {"success": False, "error": "Interactive session already running."}
        if CLAUDE_BIN is None:
            return {"success": False, "error": "Claude Code CLI ('claude') not found on PATH."}
        if not PEXPECT_AVAILABLE:
            return {"success": False, "error": "pexpect is not installed."}

        self._status = "launching"
        try:
            env = os.environ.copy()
            os.makedirs(self.working_dir, exist_ok=True)

            self._child = pexpect.spawn(
                CLAUDE_BIN,
                encoding='utf-8',
                timeout=60,
                cwd=self.working_dir,
                env=env,
            )

            # Give the terminal a moment to initialise
            time.sleep(2)
            self._child.send('\x1b]11;rgb:0000/0000/0000\x1b\\')
            self._child.send('\x1b[1;1R')
            time.sleep(3)

            # Breathe through the trust prompt if one appears
            _ = self._read_output(timeout=2)
            self._child.send('\r')
            time.sleep(4)

            startup = self._clean_output(self._read_output(timeout=2))
            self._startup_output = startup
            self._status = "ready"
            self._launched_at = datetime.now().isoformat()
            self._last_active = datetime.now().isoformat()
            self._retry_count = 0

            self._append_coding_log("system", f"Claude Code session launched. Startup: {startup[:200]}")

            syslog.info(f"Interactive Claude Code session ready (model={self.claude_model})")
            return {
                "success": True,
                "status": "ready",
                "model": self.claude_model,
                "working_dir": self.working_dir,
                "startup_output": startup,
            }
        except FileNotFoundError:
            self._status = "error"
            self._child = None
            return {"success": False, "error": "Claude Code CLI ('claude') not found on PATH."}
        except Exception as e:
            self._status = "error"
            self._child = None
            syslog.error(f"Failed to launch Claude Code: {e}")
            return {"success": False, "error": str(e)}

    def _send_prompt(self, prompt: str, wait_seconds: int = 30) -> Dict[str, Any]:
        if self._status == "uninitialized":
            result = self._launch_claude_code()
            if not result["success"]:
                return result

        if self._status == "dead":
            if self._retry_count < self._max_retries:
                syslog.info("Session dead — attempting auto-restart.")
                self._restart_claude_code()
            else:
                return {"success": False, "error": "Session dead and retries exhausted."}

        if self._status == "busy":
            return {"success": False, "error": "Claude Code session is busy. Try again shortly."}

        try:
            child = self._child
            if child is None:
                return {"success": False, "error": "No child process."}

            self._status = "busy"
            self._last_active = datetime.now().isoformat()

            self._append_coding_log("user", prompt)
            child.send(prompt + '\r')
            time.sleep(wait_seconds)

            output = self._clean_output(self._read_output(timeout=2))

            if not output and child.isalive():
                time.sleep(5)
                output = self._clean_output(self._read_output(timeout=2))

            self._last_output = output
            self._status = "ready"
            self._last_active = datetime.now().isoformat()

            self._append_coding_log("agent", output)
            return {"success": True, "output": output}

        except (pexpect.EOF, Exception) as e:
            self._status = "dead" if isinstance(e, pexpect.EOF) else "error"
            self._append_coding_log("system", f"Error: {str(e)}")
            return {"success": False, "error": str(e)}

    def _get_state(self) -> Dict[str, Any]:
        alive = self._child.isalive() if self._child is not None else False
        with self._active_proc_lock:
            active_proc = self._active_proc
            active_print_running = bool(active_proc is not None and active_proc.poll() is None)
            active_print_pid = active_proc.pid if active_print_running else None
        # Only coerce to dead when an interactive child actually exists.
        # Print-mode tasks (claude -p) intentionally run without self._child.
        if self._child is not None and not alive and self._status not in ("dead", "uninitialized", "error"):
            self._status = "dead"
        return {
            "status": self._status,
            "alive": alive,
            "model": self.claude_model,
            "working_dir": self.working_dir,
            "launched_at": self._launched_at,
            "last_active": self._last_active,
            "log_entries": len(self._coding_log),
            "last_output_preview": self._last_output[:300] if self._last_output else "",
            "active_print_running": active_print_running,
            "active_print_pid": active_print_pid,
        }

    def _cancel_active_print(self) -> Dict[str, Any]:
        with self._active_proc_lock:
            proc = self._active_proc
            if proc is None or proc.poll() is not None:
                return {"success": True, "message": "No background print task to cancel."}
            self._cancel_requested = True

        try:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=2)
            return {"success": True, "message": f"Cancelled background Claude task (pid={proc.pid})."}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            with self._active_proc_lock:
                if self._active_proc is proc:
                    self._active_proc = None

    def _kill_claude_code(self) -> Dict[str, Any]:
        if self._child is None:
            return {"success": True, "message": "No process to kill."}
        try:
            if self._child.isalive():
                self._child.send('\x03')  # Ctrl+C
                time.sleep(0.5)
                self._child.close(force=True)
            self._append_coding_log("system", "Claude Code session killed.")
            self._status = "dead"
            self._child = None
            return {"success": True, "message": "Claude Code session killed."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _safe_kill(self) -> None:
        try:
            self._kill_claude_code()
        except Exception:
            pass

    def _restart_claude_code(self) -> Dict[str, Any]:
        """Kill and relaunch the interactive session."""
        self._kill_claude_code()
        self._retry_count += 1
        if self._retry_count > self._max_retries:
            return {"success": False, "error": "Max retries exceeded."}
        return self._launch_claude_code()

    def _ensure_alive(self) -> bool:
        if self._status == "ready" and self._child is not None and self._child.isalive():
            return True
        if self._status == "uninitialized":
            result = self._launch_claude_code()
            return result["success"]
        if self._status in ("dead", "error") and self._retry_count < self._max_retries:
            result = self._restart_claude_code()
            return result["success"]
        return False

    def _setup_workflow(self, system: str = ""):
        def call_model(state: MessagesState):
            messages = [SystemMessage(content=system)] + list(state["messages"])
            prompt = self._messages_to_prompt([
                ("system", system),
                *[(getattr(m, 'type', 'human'), getattr(m, 'content', str(m)))
                  for m in state["messages"]],
            ])
            response_text = self._call_claude_print(prompt)
            return {"messages": AIMessage(content=response_text)}

        self.workflow = StateGraph(state_schema=MessagesState)
        self.workflow.add_node("model", call_model)
        self.workflow.add_edge(START, "model")
        self.memory = MemorySaver()
        self.app = self.workflow.compile(checkpointer=self.memory)


    def inference(self, messages: list, model: str = None, RAG: bool = False) -> AIMessage:
        """
        Run inference via ``claude -p``.

        Parameters
        ----------
        messages : list
            Rigel-format messages (list of tuples or dicts).
        model : str, optional
            Ignored (Claude Code uses ANTHROPIC_MODEL).
        RAG : bool, optional
            Ignored in this override (use ``inference_with_memory`` for RAG).
        """
        prompt = self._messages_to_prompt(messages)
        response_text = self._call_claude_print(prompt)
        stream_path = self._prepare_method_stream_file("inference")
        self._write_method_stream_file("inference", response_text)
        return AIMessage(content=response_text)

    def inference_stream(self, messages: list, model: str = None,
                         method_name: str = "inference",
                         stream_path: str = None) -> AIMessage:
        """
        Streaming inference via ``claude -p``.

        Because ``claude -p`` is not a true streaming endpoint we call it
        once, write the full output, and return an AIMessage — but still
        honour the Rigel stream-file contract.
        """
        prompt = self._messages_to_prompt(messages)
        response_text = self._call_claude_print(prompt)
        target_path = stream_path or self._prepare_method_stream_file(method_name)
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(response_text or "")
            f.flush()
        syslog.info(f"Streaming {method_name} complete. Written to: {target_path}")
        return AIMessage(content=response_text)

    async def inference_with_tools(self, prompt: str, tools=None) -> AIMessage:
        """
        Tool-using inference via ``claude -p``.

        Prepends ``self.continuity`` (system prompt injected by the server
        layer) and delegates to ``claude -p`` with tool + directory access.
        """
        full_prompt = f"{self.continuity}\n\nUser request:\n{prompt}"
        response_text = self._call_claude_print(
            full_prompt,
            allowed_tools="Bash,Read,Write,Edit,Glob,Grep",
            add_dir=self.working_dir,
        )
        return AIMessage(content=response_text)

    async def inference_with_tools_and_memory(self, prompt: str,
                                              thread_id: str = "default") -> AIMessage:
        """
        Tool-using inference with conversation memory.

        Prepends recent conversation history before delegating to
        ``inference_with_tools``.
        """
        history_context = self._build_tools_memory_context(thread_id)
        if history_context:
            full_prompt = (
                "Conversation history:\n"
                f"{history_context}\n\n"
                "Current user request:\n"
                f"{prompt}"
            )
        else:
            full_prompt = prompt

        response = await self.inference_with_tools(full_prompt)
        response_text = response.content if hasattr(response, "content") else str(response)

        thread_history = self.tools_memory_store.setdefault(thread_id, [])
        thread_history.append({"user": prompt, "assistant": response_text})
        if len(thread_history) > 20:
            del thread_history[:-20]

        return response

    def inference_with_memory(self, messages: list, model: str = None,
                               thread_id: str = "default", RAG: bool = True) -> AIMessage:
        """
        Conversational inference with ChromaDB memory / RAG via ``claude -p``.

        Preserves the full Rigel memory contract (session persistence,
        summarisation, RAG context injection) while using Claude Code as
        the model backend.
        """
        summerization_agent_message = """
        - Disable Reasoning: True
        - Disable think loop: True
        You are a summarization agent. You will receive data from a vectordb;
        provide a concise summary of those previous interactions.
        """
        summerization_agent_call = None

        # --- Optional summarisation of long histories ---
        if os.getenv("SUMMARIZE_CONVERSATIONS", "false").lower() == "true":
            history = self.get_conversation_history(thread_id)
            if len(history) >= 10:
                syslog.info(f"Summarizing conversation history for thread {thread_id}")
                history_text = "\n".join([
                    f"{getattr(msg, 'type', 'unknown')}: {getattr(msg, 'content', '')}"
                    for msg in history
                ])
                summary_prompt = (
                    f"{summerization_agent_message}\n\n"
                    f"Here is the conversation history:\n\n{history_text}\n\n"
                    f"Please provide a concise summary."
                )
                summary_response = self._call_claude_print(summary_prompt)
                self.vectorstore.save_session_turn(
                    session_id=thread_id,
                    user_text="Conversation Summary",
                    assistant_text=summary_response,
                    source="conversation-summary",
                )
                self.clear_memory(thread_id)

        # --- RAG context retrieval ---
        if RAG:
            syslog.info("RIGEL has previous session contexts")
            last_message = messages[-1][1] if isinstance(messages[-1], (tuple, list)) else ""
            data = self.vectorstore.search_session_context(
                session_id=thread_id, query=last_message, n_results=10
            )
            data = data.replace('{', '{{').replace('}', '}}')
            rag_prompt = (
                f"{summerization_agent_message}\n\n"
                f"Here is some retrieved context:\n\n{data}\n\n"
                f"Please provide a concise summary relevant to the user's query."
            )
            summerization_agent_call = self._call_claude_print(rag_prompt)

        # --- Build formatted messages ---
        system_message = ""
        formatted_messages: List[Any] = []
        for role, content in messages:
            if role == "system":
                current_time = datetime.now().isoformat()
                time_context = (
                    f"\n\n<CurrentTime>\nThe current system time is: {current_time}\n</CurrentTime>"
                )
                rag_summary = (
                    "\n\n<PermenantMemoryRecall>\n"
                    + summerization_agent_call
                    + "\n</PermenantMemoryRecall>"
                ) if (RAG and summerization_agent_call) else ""
                system_message = content + time_context + rag_summary
                formatted_messages.append(SystemMessage(content=system_message))
            elif role == "human":
                formatted_messages.append({"role": "user", "content": content})
            elif role == "ai":
                formatted_messages.append({"role": "assistant", "content": content})

        # --- Ensure workflow is compiled ---
        if not self.app:
            self._setup_workflow(system_message)

        # --- Invoke via LangGraph (memory checkpointing) ---
        config = {"configurable": {"thread_id": thread_id}}
        response = self.app.invoke({"messages": formatted_messages}, config=config)

        last_message = response["messages"][-1]
        human = next((msg for role, msg in messages if role == "human"), "")
        assistant = (
            last_message.content
            if hasattr(last_message, "content")
            else str(last_message)
        )

        # Persist turn to vector store
        self.vectorstore.save_session_turn(
            session_id=thread_id,
            user_text=human,
            assistant_text=assistant,
            source="conversation-history",
        )

        response_text = assistant
        self._write_method_stream_file("inference_with_memory", response_text)
        return AIMessage(content=response_text)

    # ------------------------------------------------------------------
    # Override: think (uses claude -p for reasoning loop)
    # ------------------------------------------------------------------

    def think(self, think_message: str, model: str = None) -> str:
        """
        Reasoning loop backed by Claude Code CLI.

        Iteratively calls ``inference_with_memory`` until a continuity
        breaker is detected or the maximum iteration count is reached.
        """
        self.thought_prompt = (
            "Think of the best way to do this and list it out in a short manner. "
            "Nothing more, nothing less. "
            "If the thinking process is done, say exactly 'The task is done'. "
            "If it's impossible exactly say 'The task is impossible'."
        )
        prompt_messages = [
            ("system", self.thought_prompt),
            ("human", think_message),
        ]
        max_iterations = 10
        iteration_count = 0
        while iteration_count < max_iterations:
            iteration_count += 1
            output = self.inference_with_memory(
                prompt_messages, thread_id=f"THINK{hash(think_message) % 10000}"
            )
            response_content = output.content if hasattr(output, 'content') else str(output)

            for pattern in self.continuity_patterns:
                if pattern.search(response_content):
                    syslog.info(f"Think: continuity breaker detected (iter {iteration_count})")
                    return response_content

            syslog.info(f"Think: continuing (iteration {iteration_count})")
        syslog.warning(f"Think: max iterations ({max_iterations}) reached.")
        return response_content

    # ------------------------------------------------------------------
    # Public: lifecycle
    # ------------------------------------------------------------------

    def launch(self) -> Dict[str, Any]:
        """Explicitly launch the interactive Claude Code session."""
        return self._launch_claude_code()

    def close(self) -> Dict[str, Any]:
        """Cancel active print-mode task and kill the interactive Claude Code session."""
        cancel_result = self._cancel_active_print()
        session_result = self._kill_claude_code()
        return {
            "success": bool(cancel_result.get("success")) and bool(session_result.get("success")),
            "cancel": cancel_result,
            "session": session_result,
        }

    def get_status(self) -> Dict[str, Any]:
        """Return full status of the interactive Claude Code session."""
        return self._get_state()

    def get_coding_history(self, last_n: int = 20) -> Dict[str, Any]:
        """Return the last *n* entries from the coding conversation log."""
        log = self._coding_log[-last_n:] if last_n else self._coding_log
        return {
            "total_entries": len(self._coding_log),
            "returned": len(log),
            "log": log,
        }

    def clear_coding_history(self) -> None:
        """Clear the in-memory coding log."""
        self._coding_log.clear()

    # ------------------------------------------------------------------
    # Public: high-level coding API
    # ------------------------------------------------------------------

    def coding_task(self, prompt: str) -> str:
        """
        Send a coding task to Claude Code via ``claude -p`` with full tool access.

        Uses ``claude -p`` (print mode) with ``--allowedTools`` and ``--add-dir``
        so Claude Code can read, write, edit, and execute files in the working
        directory.  Print mode is stateless and far more reliable than pexpect-
        based interactive sessions for one-shot coding tasks.
        """
        self._status = "busy"
        self._last_active = datetime.now().isoformat()
        self._append_coding_log("user", prompt)
        try:
            output = self._call_claude_print(
                prompt,
                allowed_tools="Bash,Read,Write,Edit,Glob,Grep",
                add_dir=self.working_dir,
            )
            self._last_output = output or ""
            self._last_active = datetime.now().isoformat()

            if (output or "").strip().startswith("[RigelClaude Error:"):
                self._status = "error"
                self._append_coding_log("system", output)
                raise RuntimeError(output)

            self._status = "ready"
            self._append_coding_log("agent", output or "")
            return output
        except Exception as e:
            self._status = "error"
            self._last_active = datetime.now().isoformat()
            self._append_coding_log("system", f"Error: {e}")
            raise

    def generate_code(self, specification: str, language: str = "python") -> str:
        """Generate code from a natural-language specification."""
        prompt = (
            f"Generate {language} code for the following specification.\n"
            f"Provide ONLY the code in your response, with no extra explanation "
            f"unless there are important caveats.\n"
            f"If multiple files are needed, list them clearly with file paths.\n\n"
            f"Specification:\n{specification}\n\n"
            f"Output complete, production-quality, working {language} code."
        )
        return self.coding_task(prompt)

    def review_code(self, code: str, language: str = "python") -> str:
        """Review code for bugs, security issues, style, and performance."""
        prompt = (
            f"Review the following {language} code for:\n"
            f"1. Bugs and logic errors\n"
            f"2. Security vulnerabilities\n"
            f"3. Performance optimization opportunities\n"
            f"4. Code style and best practices\n"
            f"5. Input validation issues\n\n"
            f"For each issue provide: Severity (Critical/Major/Minor), "
            f"Location, Description, Suggested fix.\n\n"
            f"Code to review:\n```{language}\n{code}\n```\n\n"
            f"Provide a structured review report."
        )
        return self.coding_task(prompt)

    def debug_code(self, code: str, error: str, language: str = "python") -> str:
        """Debug code given source and an error message."""
        prompt = (
            f"Debug the following {language} code that produces this error:\n\n"
            f"Error:\n{error}\n\n"
            f"Code:\n```{language}\n{code}\n```\n\n"
            f"Identify the root cause and provide the corrected code. "
            f"Explain what was wrong."
        )
        return self.coding_task(prompt)

    def refactor_code(self, code: str, instructions: str,
                      language: str = "python") -> str:
        """Refactor code according to specific instructions."""
        prompt = (
            f"Refactor the following {language} code according to "
            f"these instructions:\n{instructions}\n\n"
            f"Original code:\n```{language}\n{code}\n```\n\n"
            f"Provide the refactored code with a brief summary of changes made."
        )
        return self.coding_task(prompt)

    def explain_code(self, code: str, language: str = "python") -> str:
        """Explain what a piece of code does in detail."""
        prompt = (
            f"Explain the following {language} code in detail:\n\n"
            f"```{language}\n{code}\n```\n\n"
            f"Provide a line-by-line or section-by-section breakdown. "
            f"Cover: purpose, key concepts, control flow, data structures used, "
            f"and any edge cases or gotchas."
        )
        return self.coding_task(prompt)

    def execute_code_in_project(self, file_path: str,
                                args: Optional[List[str]] = None) -> str:
        """Ask Claude Code to execute a file in the working directory."""
        prompt = f"Run the file at '{file_path}'"
        if args:
            prompt += f" with arguments: {' '.join(args)}"
        prompt += "\nShow me the full output and any errors."
        return self.coding_task(prompt)
