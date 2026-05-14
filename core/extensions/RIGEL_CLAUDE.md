# RigelClaude — Claude Code Wrapper Extension

RigelClaude is a coding-specialized Rigel agent that wraps the
[Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) as its
inference backend.  It inherits the full Rigel infrastructure — MCP tools,
OS tools, ChromaDB memory / RAG, and conversation history — while delegating
all inference to Claude Code.

## Table of Contents

- [Quick Start](#quick-start)
- [How It Works](#how-it-works)
- [Configuration](#configuration)
- [API Reference](#api-reference)
  - [D-Bus Interface](#d-bus-interface)
  - [Web REST API](#web-rest-api)
  - [Python API](#python-api)
- [Architecture](#architecture)
- [Error Handling](#error-handling)
- [Docker Support](#docker-support)
- [Troubleshooting](#troubleshooting)

---

## Quick Start

### 1.  Set environment variables

Ensure the Anthropic / Claude Code API variables are exported in your
shell profile (`~/.zshrc`, `~/.bashrc`, etc.):

```bash
export ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic
export ANTHROPIC_AUTH_TOKEN=sk-your-token-here
export ANTHROPIC_MODEL=deepseek-v4-pro[1m]
export ANTHROPIC_DEFAULT_OPUS_MODEL=deepseek-v4-pro[1m]
export ANTHROPIC_DEFAULT_SONNET_MODEL=deepseek-v4-pro[1m]
export ANTHROPIC_DEFAULT_HAIKU_MODEL=deepseek-v4-flash
```

### 2.  Enable in `.env`

```ini
# RigelClaude — Claude Code wrapper extension
RIGEL_CLAUDE_ENABLED=true
```

### 3.  Start the server

```bash
# D-Bus server (default)
python dbus_server.py

# Web server
python web_server.py
```

Rigel will print:

```
RIGEL initialized with Claude Code backend (RigelClaude)
```

When `RIGEL_CLAUDE_ENABLED` is `false` (the default), Rigel uses the
normal Groq / Ollama backends and all CodingAgent endpoints return a
descriptive error.

---

## How It Works

RigelClaude operates in **two modes**:

| Mode | Mechanism | When Used |
|------|-----------|-----------|
| **Print mode** | `claude -p` via `subprocess` | `inference()`, `inference_with_memory()`, `inference_with_tools()` fallback |
| **Interactive mode** | pexpect-managed persistent `claude` session | `coding_task()`, `generate_code()`, etc. (when pexpect is available) |

### Print mode (`claude -p`)

Non-interactive, stateless.  Each call spawns a short-lived `claude -p`
process, captures stdout, and returns the cleaned text.  Used for
single-turn inference and as a fallback when the interactive session
is unavailable.

### Interactive mode (pexpect)

A long-running `claude` process is spawned via `pexpect` and kept alive
for the lifetime of the `RigelClaude` instance.  This gives the coding
agent full access to the Claude Code tool suite (Bash, Read, Write,
Edit, Glob, Grep, etc.) across multiple turns.  The session is
auto-restarted up to 3 times if it dies unexpectedly.

---

## Configuration

### Environment variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `RIGEL_CLAUDE_ENABLED` | Enable / disable the extension | `false` |
| `ANTHROPIC_BASE_URL` | Anthropic-compatible API endpoint | _(required)_ |
| `ANTHROPIC_AUTH_TOKEN` | API authentication token | _(required)_ |
| `ANTHROPIC_MODEL` | Model used for coding tasks | `claude-sonnet-4-6` |
| `ANTHROPIC_DEFAULT_OPUS_MODEL` | Opus-tier model override | _(optional)_ |
| `ANTHROPIC_DEFAULT_SONNET_MODEL` | Sonnet-tier model override | _(optional)_ |
| `ANTHROPIC_DEFAULT_HAIKU_MODEL` | Haiku-tier model override | _(optional)_ |

### Python constructor

```python
from core.extensions.rigel_claude_code_integration import RigelClaude

agent = RigelClaude(
    claude_model="deepseek-v4-pro[1m]",   # or None → reads ANTHROPIC_MODEL
    working_dir="/path/to/project",       # or None → cwd
    log_dir="/path/to/logs",              # or None → ./Logs/rigel_claude
    mcp_endpoint=default_mcp,             # MCP client for Rigel tools
    auto_launch=True,                     # spawn interactive session on init
)
```

Set `auto_launch=False` when you only need print-mode inference (e.g.
in stateless web-server handlers).  Call `agent.launch()` later to start
the interactive session on demand.

---

## API Reference

### D-Bus Interface

All methods are published on `com.rigel.RigelService`.  Inputs and
outputs are strings (complex data is JSON-serialised).

#### CodingAgentGenerateCode
```
specification: s  — natural-language code specification
language: s       — target language (default "python")
→ code: s         — generated code
```

#### CodingAgentReviewCode
```
code: s     — source code to review
language: s — language of the code
→ review: s — structured review report
```

#### CodingAgentDebugCode
```
code: s     — source code
error: s    — error message / stack trace
language: s — language of the code
→ result: s — root cause + corrected code
```

#### CodingAgentRefactorCode
```
code: s         — original source
instructions: s — what to change
language: s     — language of the code
→ result: s     — refactored code + summary
```

#### CodingAgentExplainCode
```
code: s        — source code
language: s    — language of the code
→ explanation: s — detailed breakdown
```

#### CodingAgentExecuteCode
```
file_path: s  — path to the file to execute
args_json: s  — JSON array of arguments (e.g. '["--verbose"]')
→ output: s   — execution output / errors
```

#### CodingAgentGetStatus
```
→ status_json: s — JSON object with full session state
    {
      "status": "ready|busy|dead|error|uninitialized",
      "alive": true|false,
      "model": "...",
      "working_dir": "...",
      "launched_at": "ISO-8601",
      "last_active": "ISO-8601",
      "log_entries": 42,
      "last_output_preview": "..."
    }
```

#### CodingAgentGetHistory
```
last_n: s       — number of recent entries (default "20")
→ history_json: s — JSON {total_entries, returned, log: [...]}
```

#### CodingAgentLaunch
```
→ result_json: s — {"success": true|false, ...}
```
Explicitly start the interactive session.

#### CodingAgentClose
```
→ result_json: s — {"success": true, "message": "..."}
```
Terminate the interactive session.

#### CodingAgentStatusUpdate (signal)
```
status_json: s — same shape as CodingAgentGetStatus output
```
Emitted after every coding method call.  Clients can listen passively
instead of polling.

---

### Web REST API

Base URL: `http://localhost:8000`

All coding endpoints require a valid `X-API-Key` header.  When
`RIGEL_CLAUDE_ENABLED=false`, every endpoint returns HTTP **503**
with a descriptive error.

#### `POST /coding-agent/generate-code`
```json
{ "specification": "write a quicksort", "language": "python" }
→ { "response": "<generated code>" }
```

#### `POST /coding-agent/review-code`
```json
{ "code": "def foo(): pass", "language": "python" }
→ { "response": "<review report>" }
```

#### `POST /coding-agent/debug-code`
```json
{ "code": "x = 1/0", "error": "ZeroDivisionError", "language": "python" }
→ { "response": "<root cause + fix>" }
```

#### `POST /coding-agent/refactor-code`
```json
{ "code": "...", "instructions": "add type hints", "language": "python" }
→ { "response": "<refactored code>" }
```

#### `POST /coding-agent/explain-code`
```json
{ "code": "...", "language": "python" }
→ { "response": "<detailed explanation>" }
```

#### `POST /coding-agent/execute-code`
```json
{ "file_path": "/app/main.py", "args": ["--verbose"] }
→ { "response": "<execution output>" }
```

#### `GET /coding-agent/status`
```json
{
  "status": "ready",
  "alive": true,
  "model": "deepseek-v4-pro[1m]",
  "working_dir": "/home/zerone/Documents/RIGEL",
  "launched_at": "2026-05-12T...",
  "last_active": "2026-05-12T...",
  "log_entries": 15,
  "last_output_preview": "..."
}
```

#### `GET /coding-agent/history?last_n=20`
```json
{
  "total_entries": 42,
  "returned": 20,
  "log": [
    { "timestamp": "...", "role": "user", "message": "..." },
    { "timestamp": "...", "role": "agent", "message": "..." }
  ]
}
```

#### `POST /coding-agent/launch`
```json
{ "success": true, "status": "ready", "model": "...", ... }
```

#### `POST /coding-agent/close`
```json
{ "success": true, "message": "Claude Code session killed." }
```

---

### Python API

The full `RigelClaude` class is available for direct use:

```python
from core.extensions.rigel_claude_code_integration import RigelClaude

agent = RigelClaude(auto_launch=False)

# ---- Inference (print mode) ----
from langchain_core.messages import AIMessage
response: AIMessage = agent.inference([
    ("system", "You are a helpful assistant."),
    ("human", "What is Python?")
])
print(response.content)

# ---- Coding tasks (interactive mode, with tools) ----
code = agent.generate_code("a REST API client in Python", language="python")
review = agent.review_code(code, "python")
fix = agent.debug_code(code, "NameError: name 'requests' is not defined")
refactored = agent.refactor_code(code, "add async/await support")
explanation = agent.explain_code(code)

# ---- Session management ----
agent.launch()                     # start interactive session
print(agent.get_status())          # check state
print(agent.get_coding_history(10))  # last 10 log entries
agent.close()                      # kill session
```

#### Method inventory

| Method | Returns | Description |
|--------|---------|-------------|
| `inference(messages)` | `AIMessage` | Single-turn via `claude -p` |
| `inference_stream(messages)` | `AIMessage` | Streaming, writes to file |
| `inference_with_tools(prompt)` | `AIMessage` | Tool-using; routes coding tasks to interactive session |
| `inference_with_memory(messages, thread_id)` | `AIMessage` | Conversational with ChromaDB RAG |
| `inference_with_tools_and_memory(prompt, thread_id)` | `AIMessage` | Tool-using with conversation history |
| `think(message)` | `str` | Multi-iteration reasoning loop |
| `generate_code(spec, language)` | `str` | Code from natural language |
| `review_code(code, language)` | `str` | Structured code review |
| `debug_code(code, error, language)` | `str` | Root cause + fix |
| `refactor_code(code, instructions, language)` | `str` | Refactored code |
| `explain_code(code, language)` | `str` | Detailed explanation |
| `execute_code_in_project(file_path, args)` | `str` | Execute file via Claude Code |
| `coding_task(prompt, wait_seconds)` | `str` | Raw prompt to interactive session |
| `launch()` | `dict` | Start interactive session |
| `close()` | `dict` | Kill interactive session |
| `get_status()` | `dict` | Session state |
| `get_coding_history(last_n)` | `dict` | Conversation log |
| `clear_coding_history()` | — | Clear in-memory log |

---

## Architecture

```
                          ┌─────────────────────────┐
                          │    Rigel Server Layer    │
                          │  (dbus_server / web)     │
                          └──────────┬──────────────┘
                                     │
                          ┌──────────▼──────────────┐
                          │      RigelClaude        │
                          │  (core/extensions/...)  │
                          ├─────────────────────────┤
                          │  Inherits: Rigel        │
                          │  • MCP tools            │
                          │  • OS tools             │
                          │  • ChromaDB memory/RAG  │
                          │  • conversation history │
                          ├──────────┬──────────────┤
                          │          │              │
                    ┌─────▼────┐ ┌───▼────────┐
                    │ claude -p│ │ pexpect    │
                    │(print)   │ │(interactive│
                    │subprocess│ │ session)   │
                    └──────────┘ └────────────┘
```

**Inheritance**: `Rigel` ← `RigelClaude`

`RigelClaude` inherits **directly** from `Rigel` — no Ollama or Groq
dependency.  The base class `self.llm` is `None`; all inference methods
are overridden to use the Claude Code CLI instead.

The `_setup_workflow()` override replumbs the LangGraph state graph so
that the model node calls `claude -p` instead of `self.llm.invoke()`.
This preserves the full LangGraph memory checkpointing and ChromaDB
persistence without requiring a LangChain LLM.

---

## Error Handling

All public methods wrap errors predictably:

- **Print mode** (`claude -p` failures): Return strings prefixed with
  `[RigelClaude Error: ...]` for easy downstream detection.
- **Interactive mode** (pexpect failures): Return `{"success": false,
  "error": "..."}` dicts.  On session death, auto-restart is attempted
  up to 3 times.
- **Server endpoints** (when disabled): Return HTTP 503 or D-Bus error
  JSON with a clear message.

The agent **always** remains usable as a fallback: if the interactive
session dies and retries are exhausted, `coding_task()` falls back to
`claude -p` with tool permissions.

---

## Docker Support

The `docker-compose.yml` has been updated with:

- **Binary mount**: `/usr/bin/claude` is mounted read-only into the
  container (same pattern as the `ollama` binary mount).
- **Environment passthrough**: All `ANTHROPIC_*` variables and
  `RIGEL_CLAUDE_ENABLED` are forwarded to the container.

Enable in Docker:

```bash
RIGEL_CLAUDE_ENABLED=true docker compose up
```

Make sure the `ANTHROPIC_*` variables are exported in your shell
before running `docker compose` (or add them to `.env`).

---

## Troubleshooting

### `[RigelClaude Error: Claude Code CLI not found on PATH.]`

The `claude` binary is not installed or not in `PATH`.  Install
Claude Code:

```bash
npm install -g @anthropic-ai/claude-code
```

Verify:

```bash
which claude   # → /usr/bin/claude (or similar)
claude --version
```

### `[RigelClaude Error: Claude Code exited 1: ...]`

Claude Code ran but returned a non-zero exit code.  Check:

- `ANTHROPIC_AUTH_TOKEN` is set and valid
- `ANTHROPIC_BASE_URL` is correct and reachable
- The model name in `ANTHROPIC_MODEL` is valid

### "RigelClaude is not enabled. Set RIGEL_CLAUDE_ENABLED=true in .env"

The extension is disabled.  Set `RIGEL_CLAUDE_ENABLED=true` in `.env`
and restart the server.

### "pexpect not available — interactive session disabled"

`pexpect` is not installed.  Install it:

```bash
pip install pexpect
```

Print mode (`claude -p`) still works without pexpect.

### Interactive session dies frequently

- Increase `wait_seconds` in `coding_task()` for long-running tasks.
- Check that the Claude Code CLI can run in your terminal normally
  (`claude` without `-p`).
- Look at the coding log files in `Logs/rigel_claude/` for the
  conversation history leading up to the crash.
