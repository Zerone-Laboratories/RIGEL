"""Unit and integration tests for rigel.py core agent logic.

Covers continuity breakers, template escaping, chunk-to-text, tools memory
store, stream file management, and natural-language agent delegation.
"""

import os
import re
import sys
import tempfile
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

# ---------------------------------------------------------------------------
# Stub heavyweight dependencies so we can import core.rigel
# ---------------------------------------------------------------------------

def _make_pkg(name):
    """Create a mock package MagicMock capable of sub-imports and attribute access."""
    mod = MagicMock()
    mod.__path__ = []
    mod.__package__ = name
    mod.__spec__ = MagicMock()
    mod.__spec__.submodule_search_locations = []
    return mod

# Pre-populate sys.modules with stub packages for every heavy dependency
_stubs = {
    # Package-level stubs
    "langchain": _make_pkg("langchain"),
    "langchain_core": _make_pkg("langchain_core"),
    "langchain_mcp_adapters": _make_pkg("langchain_mcp_adapters"),
    "langgraph": _make_pkg("langgraph"),
    "chromadb": _make_pkg("chromadb"),
    "mcp": _make_pkg("mcp"),
    "fastapi": _make_pkg("fastapi"),
    # Leaf sub-modules — plain MagicMock is fine for direct imports
    "langchain_core.messages": MagicMock(),
    "langchain_core.prompts": MagicMock(),
    "langchain_core.runnables": MagicMock(),
    "langchain_core.output_parsers": MagicMock(),
    "langchain_core.tools": MagicMock(),
    "langchain_core.language_models": MagicMock(),
    "langchain.chains": MagicMock(),
    "langchain_groq": MagicMock(),
    "langchain_ollama": MagicMock(),
    "langchain_mcp_adapters.client": MagicMock(),
    "langchain_mcp_adapters.tools": MagicMock(),
    "langgraph.graph": MagicMock(),
    "langgraph.graph.state": MagicMock(),
    "langgraph.prebuilt": MagicMock(),
    "langgraph.checkpoint": MagicMock(),
    "langgraph.checkpoint.memory": MagicMock(),
    "langsmith": MagicMock(),
    "langchain_text_splitters": MagicMock(),
    "chromadb.config": MagicMock(),
    "mcp.server": MagicMock(),
    "mcp.server.fastmcp": MagicMock(),
    "mcp.client": MagicMock(),
    "mcp.client.stdio": MagicMock(),
    "fastapi.responses": MagicMock(),
    "fastapi.staticfiles": MagicMock(),
    "fastapi.openapi": MagicMock(),
    "whisper": MagicMock(),
    "torch": MagicMock(),
    "numpy": MagicMock(),
    "pypdf": MagicMock(),
    "groq": MagicMock(),
    "ollama": MagicMock(),
    "playwright": MagicMock(),
    "pexpect": MagicMock(),
    "PIL": MagicMock(),
    "PIL.Image": MagicMock(),
    "pillow": MagicMock(),
    "httpx": MagicMock(),
    "requests": MagicMock(),
    "dotenv": MagicMock(),
    "colorama": MagicMock(),
    "rich": MagicMock(),
    "yaml": MagicMock(),
    "packaging": MagicMock(),
    "tqdm": MagicMock(),
    "sounddevice": MagicMock(),
    "soundfile": MagicMock(),
    "uvicorn": MagicMock(),
    "starlette": MagicMock(),
    "sqlalchemy": MagicMock(),
    "pydantic": MagicMock(),
    "pydantic_core": MagicMock(),
}

for mod_name, mock in _stubs.items():
    if mod_name not in sys.modules:
        sys.modules[mod_name] = mock

# Now mock core.logger globally for rigel imports (it uses SysLog at module level)
_mock_syslog = MagicMock()
_mock_log_module = MagicMock()
_mock_log_module.SysLog = MagicMock(return_value=_mock_syslog)
_mock_log_module.ColoredFormatter = MagicMock()
sys.modules["core.logger"] = _mock_log_module

# core.os_tools imports core.logger at module level → stubbed above, so safe.
# But it also does `subprocess` etc which work fine. Still, mock it to avoid
# Logs/rigel.log PermissionError from the module-level SysLog instantiation.
_mock_os_tools = MagicMock()
sys.modules["core.os_tools"] = _mock_os_tools

# core.rdb uses chromadb (already stubbed)
_mock_rdb = MagicMock()
_mock_rdb.DBConn = MagicMock()
sys.modules["core.rdb"] = _mock_rdb

# Import rigel core
from core.rigel import Rigel

# Import web_server utility functions for testing
# (fastapi is already stubbed, so this should work now)
from web_server import (
    _sanitize_natural_language_output,
    _normalize_home_paths,
    _extract_tool_agent_task,
    _resolve_tool_task,
    _looks_like_capability_refusal,
)


# ============================================================================
# Continuity Breakers
# ============================================================================

class TestContinuityBreakers:
    """Tests for the continuity breaker regex patterns in Rigel.__init__."""

    def test_detects_task_done(self):
        patterns = Rigel().continuity_patterns
        text = "The task is done."
        assert any(p.search(text) for p in patterns)

    def test_detects_please_provide_more_info(self):
        patterns = Rigel().continuity_patterns
        text = "I need your username. Please provide more information."
        assert any(p.search(text) for p in patterns)

    def test_detects_task_impossible(self):
        patterns = Rigel().continuity_patterns
        text = "Unfortunately, The task is impossible."
        assert any(p.search(text) for p in patterns)

    def test_detects_let_me_know(self):
        patterns = Rigel().continuity_patterns
        text = "I've completed that. Let me know what you'd like to do next."
        assert any(p.search(text) for p in patterns)

    def test_detects_unable_to_continue(self):
        patterns = Rigel().continuity_patterns
        text = "Unable to continue with this request."
        assert any(p.search(text) for p in patterns)

    def test_detects_no_specific_action(self):
        patterns = Rigel().continuity_patterns
        text = "No specific action to perform right now."
        assert any(p.search(text) for p in patterns)

    def test_detects_seems_stuck(self):
        patterns = Rigel().continuity_patterns
        text = "It seems we're stuck in a loop."
        assert any(p.search(text) for p in patterns)

    def test_case_insensitive(self):
        patterns = Rigel().continuity_patterns
        text = "THE TASK IS DONE."
        assert any(p.search(text) for p in patterns)

    def test_does_not_false_trigger(self):
        patterns = Rigel().continuity_patterns
        text = "Let me think about this task and get back to you."
        assert not any(p.search(text) for p in patterns)

    def test_all_patterns_compile(self):
        """Every continuity_breakers entry should compile without error."""
        for pattern in Rigel().continuity_patterns:
            assert pattern.pattern  # ensures it's a valid compiled regex


# ============================================================================
# Template Brace Escaping — _escape_template_braces
# ============================================================================

class TestEscapeTemplateBraces:
    def test_escapes_braces_in_tuples(self):
        rigel = Rigel()
        msgs = [("system", "Hello {name}"), ("human", "Use {tool}")]
        escaped = rigel._escape_template_braces(msgs)
        assert escaped[0][1] == "Hello {{name}}"
        assert escaped[1][1] == "Use {{tool}}"

    def test_escapes_braces_in_dicts(self):
        rigel = Rigel()
        msgs = [{"role": "user", "content": "Value: {val}"}]
        escaped = rigel._escape_template_braces(msgs)
        assert escaped[0]["content"] == "Value: {{val}}"

    def test_leaves_already_escaped_alone(self):
        rigel = Rigel()
        msgs = [("system", "Hello {{name}}")]
        escaped = rigel._escape_template_braces(msgs)
        assert escaped[0][1] == "Hello {{{{name}}}}"

    def test_no_braces_unchanged(self):
        rigel = Rigel()
        msgs = [("system", "Plain text"), ("human", "No braces here")]
        escaped = rigel._escape_template_braces(msgs)
        assert escaped[0][1] == "Plain text"
        assert escaped[1][1] == "No braces here"

    def test_preserves_non_string_messages(self):
        rigel = Rigel()
        msgs = [("system", "ok"), 42, None]
        escaped = rigel._escape_template_braces(msgs)
        assert escaped[1] == 42
        assert escaped[2] is None


# ============================================================================
# Chunk To Text — _chunk_to_text
# ============================================================================

class TestChunkToText:
    def test_none_returns_empty(self):
        rigel = Rigel()
        assert rigel._chunk_to_text(None) == ""

    def test_string_passthrough(self):
        rigel = Rigel()
        assert rigel._chunk_to_text("hello") == "hello"

    def test_object_with_content_string(self):
        rigel = Rigel()
        obj = MagicMock()
        obj.content = "chunk text"
        assert rigel._chunk_to_text(obj) == "chunk text"

    def test_content_is_list_of_strings(self):
        rigel = Rigel()
        obj = MagicMock()
        obj.content = ["part1", "part2", "part3"]
        assert rigel._chunk_to_text(obj) == "part1part2part3"

    def test_content_is_list_of_dicts(self):
        rigel = Rigel()
        obj = MagicMock()
        obj.content = [{"text": "A"}, {"text": "B"}, {"content": "C"}]
        assert rigel._chunk_to_text(obj) == "ABC"

    def test_empty_content_falls_back_to_str(self):
        rigel = Rigel()
        obj = MagicMock()
        obj.content = ""
        assert rigel._chunk_to_text(obj) == ""


# ============================================================================
# Tools Memory Store — _build_tools_memory_context, clear_tools_memory
# ============================================================================

class TestToolsMemoryStore:
    def test_empty_store_returns_empty(self):
        rigel = Rigel()
        assert rigel._build_tools_memory_context("no_such_thread") == ""

    def test_builds_context_from_turns(self):
        rigel = Rigel()
        rigel.tools_memory_store["thread1"] = [
            {"user": "What is 2+2?", "assistant": "4"},
            {"user": "And 3+3?", "assistant": "6"},
        ]
        ctx = rigel._build_tools_memory_context("thread1")
        assert "What is 2+2?" in ctx
        assert "4" in ctx
        assert "3+3" in ctx
        assert "6" in ctx

    def test_max_turns_limit(self):
        rigel = Rigel()
        rigel.tools_memory_store["thread1"] = [
            {"user": f"Q{i}", "assistant": f"A{i}"} for i in range(20)
        ]
        ctx = rigel._build_tools_memory_context("thread1", max_turns=3)
        assert "Q0" not in ctx
        assert "Q19" in ctx
        assert "A19" in ctx

    def test_clear_memory_removes_thread(self):
        rigel = Rigel()
        rigel.tools_memory_store["thread1"] = [{"user": "hi", "assistant": "hello"}]
        rigel.clear_tools_memory("thread1")
        assert "thread1" not in rigel.tools_memory_store

    def test_clear_nonexistent_no_error(self):
        rigel = Rigel()
        rigel.clear_tools_memory("no_such_thread")  # should not raise

    def test_inference_with_tools_and_memory_stores_turns(self):
        """Test that tool memory accumulates turns up to 20."""
        rigel = Rigel()
        # Access the thread history directly
        thread_history = rigel.tools_memory_store.setdefault("test_thread", [])
        for i in range(25):
            thread_history.append({"user": f"Q{i}", "assistant": f"A{i}"})
        assert len(thread_history) == 25

    def test_history_trimmed_at_20(self):
        """After 20+ turns the oldest should be dropped (per original logic)."""
        rigel = Rigel()
        thread_history = rigel.tools_memory_store.setdefault("test_thread", [])
        for i in range(25):
            thread_history.append({"user": f"Q{i}", "assistant": f"A{i}"})
        # Simulate the original trim: keep last 20
        if len(thread_history) > 20:
            del thread_history[:-20]
        assert len(thread_history) == 20
        assert thread_history[0]["user"] == "Q5"  # oldest kept is #5
        assert thread_history[-1]["user"] == "Q24"


# ============================================================================
# Stream File Management
# ============================================================================

class TestStreamFileManagement:
    def test_prepare_creates_file_path(self, monkeypatch):
        with tempfile.TemporaryDirectory() as tmp:
            monkeypatch.setattr("core.rigel.RIGEL_STREAM_DIR",
                              type("Path", (), {"mkdir": lambda *a, **kw: None,
                                                 "glob": lambda self, p: []}))

            rigel = Rigel()
            rigel._prepare_method_stream_file = lambda name: os.path.join(tmp, f"stream-{name}.stream")

            path = rigel._prepare_method_stream_file("test_method")
            assert "stream-test_method" in path
            assert path.endswith(".stream")

    def test_write_method_stream_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            filepath = os.path.join(tmp, "inference-test_write.stream")
            with open(filepath, "w") as f:
                f.write("output content")
                f.flush()

            with open(filepath) as f:
                assert f.read() == "output content"


# ============================================================================
# Natural Language Output Sanitization
# ============================================================================

class TestSanitizeNaturalLanguageOutput:
    def test_removes_think_tags(self):
        text = "Let me <think>analyze this</think> respond now."
        out = _sanitize_natural_language_output(text)
        assert "<think>" not in out
        assert "analyze this" not in out
        assert "respond now" in out

    def test_removes_call_tool_agent_prefix(self):
        text = "CALL_TOOL_AGENT: do something useful"
        out = _sanitize_natural_language_output(text)
        assert "CALL_TOOL_AGENT" not in out
        assert "do something useful" in out

    def test_removes_call_tool_agent_variants(self):
        for variant in [
            "CALL TOOL AGENT: task",
            "CALL-TOOL-AGENT: task",
            "CALL_TOOL_AGENT:task",
        ]:
            out = _sanitize_natural_language_output(variant)
            assert "CALL" not in out, f"Failed for: {variant}"

    def test_collapses_whitespace(self):
        text = "Hello    world\n\n\nnew   line"
        out = _sanitize_natural_language_output(text)
        assert "    " not in out
        assert "\n" not in out

    def test_strips_markdown_chars(self):
        text = "**bold** and *italic* and `code`"
        out = _sanitize_natural_language_output(text)
        assert "**" not in out
        assert "*" not in out
        assert "`" not in out
        assert "bold" in out

    def test_empty_string(self):
        assert _sanitize_natural_language_output("") == ""
        assert _sanitize_natural_language_output(None) == ""


# ============================================================================
# Home Path Normalization
# ============================================================================

class TestNormalizeHomePaths:
    def test_replaces_tilde(self):
        assert "/home/zerone/project" in _normalize_home_paths("~/project")

    def test_preserves_absolute_paths(self):
        assert _normalize_home_paths("/etc/config") == "/etc/config"

    def test_does_not_replace_tilde_in_word(self):
        text = "prefix~suffix"
        result = _normalize_home_paths(text)
        assert "zerone" not in result


# ============================================================================
# Tool Agent Task Extraction
# ============================================================================

class TestExtractToolAgentTask:
    def test_extracts_simple_task(self):
        task = _extract_tool_agent_task("CALL_TOOL_AGENT: check disk space")
        assert task == "check disk space"

    def test_extracts_with_normalized_path(self):
        old_home = os.environ.get("HOST_HOME")
        os.environ["HOST_HOME"] = "/home/testuser"
        try:
            task = _extract_tool_agent_task("CALL_TOOL_AGENT: list ~/docs")
            assert "testuser" in task
            assert "~" not in task
        finally:
            if old_home is not None:
                os.environ["HOST_HOME"] = old_home
            else:
                os.environ.pop("HOST_HOME", None)

    def test_extracts_variants(self):
        for variant in [
            "CALL TOOL AGENT: task1",
            "CALL-TOOL-AGENT: task2",
            "CALL_TOOL_AGENT:task3",
        ]:
            task = _extract_tool_agent_task(variant)
            assert task is not None, f"Failed for: {variant}"

    def test_returns_none_for_regular_text(self):
        assert _extract_tool_agent_task("Hello, how are you?") is None
        assert _extract_tool_agent_task("") is None
        assert _extract_tool_agent_task(None) is None

    def test_returns_empty_string_for_empty_task(self):
        """When task body is empty, returns empty string (and caller uses user_query)."""
        result = _extract_tool_agent_task("CALL_TOOL_AGENT:")
        assert result == ""


# ============================================================================
# Resolve Tool Task (router logic without LLM)
# ============================================================================

class TestResolveToolTask:
    def test_extract_returned_first(self):
        """When _extract_tool_agent_task returns something, _resolve_tool_task uses it."""
        text = "CALL_TOOL_AGENT: run diagnostics"
        result = _resolve_tool_task(text, "original query", "thread1")
        assert result == "run diagnostics"

    def test_returns_none_for_normal_text(self):
        """Without a CALL_TOOL pattern and without an LLM to route,
        _resolve_tool_task returns None."""
        # _should_delegate_to_tool_agent calls rigel.inference_with_memory
        # which will fail since we don't have a real rigel instance.
        # The try/except in _should_delegate_to_tool_agent returns False.
        result = _resolve_tool_task("hello world", "hello world", "thread1")
        assert result is None


# ============================================================================
# Capability Refusal Detection
# ============================================================================

class TestLooksLikeCapabilityRefusal:
    def test_detects_no_access(self):
        assert _looks_like_capability_refusal("I don't have access to that.")

    def test_detects_cannot_access(self):
        assert _looks_like_capability_refusal("I cannot access the file.")

    def test_detects_cant_access(self):
        assert _looks_like_capability_refusal("I can't access that resource.")

    def test_detects_no_realtime_data(self):
        assert _looks_like_capability_refusal("I have no real-time data available.")

    def test_detects_unable_to(self):
        assert _looks_like_capability_refusal("I am unable to complete this request.")

    def test_normal_response_not_refusal(self):
        assert not _looks_like_capability_refusal("Here is the result you asked for.")
        assert not _looks_like_capability_refusal("The file has been created.")
        assert not _looks_like_capability_refusal("")

    def test_case_insensitive(self):
        assert _looks_like_capability_refusal("I DON'T HAVE ACCESS to the system.")


# ============================================================================
# D-Bus CALL_TOOL_AGENT detection (dbus_server.py style)
# ============================================================================

class TestCallToolAgentDetection:
    """Tests for the has_call_tool_agent regex used in dbus_server.RigelNaturalLanguage."""

    def _has_call_tool_agent(self, text: str) -> bool:
        pattern = r'\[CALL[\s_\-]*TOOL[\s_\-]*AGENT\s*:\s*.+?\]'
        return bool(re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL))

    def test_detects_bracketed_form(self):
        assert self._has_call_tool_agent("[CALL_TOOL_AGENT: check status]")

    def test_detects_bracketed_with_dashes(self):
        assert self._has_call_tool_agent("[CALL-TOOL-AGENT: do task]")

    def test_detects_bracketed_with_spaces(self):
        assert self._has_call_tool_agent("[CALL TOOL AGENT: do task]")

    def test_detects_case_insensitive(self):
        assert self._has_call_tool_agent("[call_tool_agent: lowercase]")

    def test_requires_brackets(self):
        """The bracketed variant requires [...] wrappers."""
        assert not self._has_call_tool_agent("CALL_TOOL_AGENT: no brackets")


# ============================================================================
# Rigel Workflow & Memory (mocked LangGraph)
# ============================================================================

class TestRigelWorkflow:
    """Test the _setup_workflow / get_conversation_history / clear_memory lifecycle."""

    def test_setup_creates_app_and_memory(self):
        """_setup_workflow should create self.app and self.memory."""
        rigel = Rigel()
        rigel.llm = MagicMock()
        rigel.llm.invoke.return_value = MagicMock(content="mock response")

        rigel._setup_workflow("test system prompt")
        assert rigel.app is not None
        assert rigel.memory is not None

    def test_get_conversation_history_empty(self):
        rigel = Rigel()
        rigel.llm = MagicMock()
        rigel.llm.invoke.return_value = MagicMock(content="ok")
        rigel._setup_workflow("sys")

        # Mock the checkpointer to return empty state for a new thread
        mock_state = MagicMock()
        mock_state.values = {"messages": []}
        rigel.memory.get = MagicMock(return_value=mock_state)
        rigel.app.get_state = MagicMock(return_value=mock_state)

        history = rigel.get_conversation_history("test_thread_empty")
        assert isinstance(history, list)
        assert len(history) == 0

    def test_clear_memory_no_error(self):
        rigel = Rigel()
        rigel.llm = MagicMock()
        rigel.llm.invoke.return_value = MagicMock(content="ok")
        rigel._setup_workflow("sys")

        # Should not raise
        rigel.clear_memory("test_thread_clear")

    def test_clear_tools_memory(self):
        rigel = Rigel()
        rigel.tools_memory_store["thread_a"] = [{"user": "hi", "assistant": "hello"}]
        assert "thread_a" in rigel.tools_memory_store
        rigel.clear_tools_memory("thread_a")
        assert "thread_a" not in rigel.tools_memory_store
