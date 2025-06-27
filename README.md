# RIGEL - Open Source AI Assistant & Multi-LLM Agentic Engine

<div align="center">
  <img src="assets/rigel_logo.png" alt="RIGEL AI Assistant Logo - Open Source Multi-LLM Engine" width="300"/>
  
  [![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
  [![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
  [![Ollama](https://img.shields.io/badge/Ollama-Compatible-green.svg)](https://ollama.ai)
  [![Groq](https://img.shields.io/badge/Groq-Supported-orange.svg)](https://groq.com)
</div>

## Table of Contents

- [Overview](#overview)
- [Project Status](#project-status)
- [Features](#features)
- [Supported Backends](#supported-backends)
- [Installation](#installation)
- [Quick Start](#quick-start)
  - [Main Launcher (Recommended)](#main-launcher-recommended)
  - [D-Bus Server (Linux Desktop Integration)](#d-bus-server-linux-desktop-integration)
  - [Web Server (HTTP REST API)](#web-server-http-rest-api)
  - [Starting the MCP Server](#starting-the-mcp-server-on-a-separate-instance)
  - [Configuring MCP Servers](#configuring-mcp-servers)
  - [Using the D-Bus Service](#using-the-d-bus-service)
- [Voice Features](#voice-features)
  - [Voice Synthesis (Text-to-Speech)](#voice-synthesis-text-to-speech)
  - [Voice Recognition (Speech-to-Text)](#voice-recognition-speech-to-text)
  - [Voice Requirements](#voice-requirements)
  - [D-Bus Voice Endpoints](#d-bus-voice-endpoints)
- [Basic Usage Examples](#basic-usage-with-ollama)
  - [Usage with Ollama](#basic-usage-with-ollama)
  - [Usage with Groq](#basic-usage-with-groq)
  - [Usage with Memory](#usage-with-memory)
- [Project Structure](#project-structure)
- [API Reference](#api-reference)
- [Message Format](#message-format)
- [RAG (Retrieval-Augmented Generation)](#rag-retrieval-augmented-generation)
- [MCP (Model Context Protocol) Tools](#mcp-model-context-protocol-tools)
  - [Key MCP Capabilities](#key-mcp-capabilities)
  - [MCP Server Configuration](#mcp-server-configuration)
  - [Available MCP Tools](#available-mcp-tools)
  - [MCP Usage Examples](#mcp-usage-examples)
  - [MCP Setup Instructions](#mcp-setup-instructions)
- [D-Bus Server](#d-bus-server-1)
  - [D-Bus Interface Details](#d-bus-interface-details)
  - [Available D-Bus Endpoints](#available-d-bus-endpoints)
  - [Running the D-Bus Server](#running-the-d-bus-server)
  - [D-Bus Client Examples](#d-bus-client-examples)
- [Web Server](#web-server)
  - [Web API Endpoints](#web-api-endpoints)
  - [Running the Web Server](#running-the-web-server)
  - [Web API Usage Examples](#web-api-usage-examples)
- [Environment Variables](#environment-variables)
- [Logging](#logging)
- [Contributing](#contributing)
- [License](#license)
- [Support](#support)

---

Hello World !

> Zerone Laboratories - Rigel Engine v4.0.X [Developer Beta]

**Open-source Hybrid AI Assistant & Virtual Assistant Engine**  
Multi-LLM backend support | Agentic AI | Local & Cloud Inference | D-Bus Integration | Python AI Framework

Powered by multiple LLM backends (Ollama, Groq, LLAMA.cpp), designed for flexible AI inference, decision-making, and system integration.

- Agentic Inference + Natural conversation
- Plug-and-play multi-LLM support
- DBus interface for OS-level integration
- Modular, extensible, and developer-friendly
- Build it. Hack it. Make it yours.

**What makes RIGEL special?**
RIGEL bridges the gap between powerful AI models and practical system integration. Whether you're building a personal AI assistant, developing chatbots, creating AI-powered applications, or researching agentic AI systems, RIGEL provides the foundation you need with support for both local privacy-focused inference and high-performance cloud models.

> [!WARNING]
> RIGEL Engine is still in developer-beta stage. Bugs may present. The code will be well structured in the public release and more features will be added!.

## Example Tool built using RIGEL Engine
### Rigel-Runtime Shell

<div align="center">
  <img src="assets/Demo.gif" alt="RIGEL Demo" width="800"/>
</div>

Repository for this tool: [https://github.com/Zerone-Laboratories/RIGEL-Runtime]

## Overview

RIGEL is a powerful **open-source multi-agentic AI engine** and **virtual assistant framework** that provides a unified interface for multiple language model backends. Built with extensibility in mind, it supports both **local AI inference via Ollama** and **cloud-based inference through Groq**. 

**Perfect for developers building AI applications, chatbots, virtual assistants, and agentic AI systems.**

Key capabilities:
- **Multi-LLM Support**: Ollama (local), Groq (cloud), LLAMA.cpp, Transformers
- **Agentic AI**: Advanced reasoning, thinking, and decision-making
- **System Integration**: D-Bus server for OS-level AI assistance  
- **MCP Tools**: File management, system commands, real-time information with configurable server support
- **Voice Interface**: Local speech-to-text and text-to-speech capabilities
- **Memory Management**: Persistent conversation threads
- **Extensible**: Plugin architecture for custom capabilities and MCP server integration

Aims to act as a central AI server for multiple agentic-based clients and AI-powered applications.


## Project Status

| Feature | Status |
|---------|--------|
| Inference with Ollama | ✓ |
| Inference with Groq | ✓ |
| Inference with LLAMA.cpp (CUDA/Vulkan Compute) | - |
| Inference with transformers | - |
| Thinking | ✓ |
| MCP | ✓ |
| Dbus Server | ✓ |
| RAG | Partial |
| Memory | ✓ |
| Local Voice Recognition | ✓ |
| Local Voice Synthesis | ✓ |
| Multiple Request Handling | Un-Tested |


## Features

- **Multi-Backend Support**: Seamlessly switch between Ollama (local) and Groq (cloud) backends. More backends will be integrated in future
- **D-Bus Server Integration**: Inter-process communication via D-Bus for system-wide AI assistance
- **MCP (Model Context Protocol) Tools**: Extended AI capabilities with system-level operations including file management, system commands, and real-time information access
- **Voice Synthesis & Recognition**: Local speech-to-text using Whisper and text-to-speech using Piper with chunked streaming audio
- **Extensible Architecture**: Built with a superclass design for easy extension to new capabilities
- **Memory Management**: Persistent conversation memory with thread-based organization
- **Advanced Thinking**: Sophisticated reasoning and decision-making capabilities
- **Comprehensive Logging**: Integrated logging system for debugging and monitoring
- **Flexible Inference**: Support for custom prompts and message formats
- **RAG Support**: Retrieval-Augmented Generation using ChromaDB for document-based AI interactions

## Supported Backends

### Ollama Backend (`RigelOllama`)
- **Default Model**: `llama3.2`
- **Type**: Local inference
- **Benefits**: Privacy, no API costs, offline capability

### Groq Backend (`RigelGroq`)
- **Default Model**: `llama3-70b-8192`
- **Type**: Cloud-based inference
- **Benefits**: High performance, larger models, no local compute requirements
- **Requirements**: Groq API key

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd RIGEL
```

2. Create and activate a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Linux/macOS
# or
.venv\Scripts\activate     # On Windows
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. For voice features, install system dependencies:
```bash
# Install Piper TTS (for voice synthesis)
# Download from: https://github.com/rhasspy/piper/releases
# Or install via package manager if available

# Install PulseAudio for audio playback (Ubuntu/Debian)
sudo apt-get install pulseaudio pulseaudio-utils

# Install PulseAudio for audio playback (Fedora/RHEL) 
sudo dnf install pulseaudio pulseaudio-utils
```

5. For Ollama backend, ensure Ollama is installed and running:
```bash
# Install Ollama (if not already installed)
curl -fsSL https://ollama.ai/install.sh | sh

# Pull the default model
ollama pull llama3.2
```

6. For D-Bus functionality (Linux only), ensure system dependencies:
```bash
# Ubuntu/Debian
sudo apt-get install python3-gi python3-gi-cairo gir1.2-gtk-3.0

# Fedora/RHEL
sudo dnf install python3-gobject python3-gobject-cairo gtk3-devel
```

## Quick Start

RIGEL offers two server modes to suit different use cases and environments:

### Main Launcher (Recommended)

Use the main launcher to easily choose between server modes:

```bash
python main.py
```

This will present you with options to run either the D-Bus server or Web server, with automatic dependency checking and helpful setup instructions.

### D-Bus Server (Linux Desktop Integration)

RIGEL's D-Bus server provides system-wide AI assistance with advanced tool capabilities, perfect for Linux desktop integration.

**Best for:**
- Linux desktop environments
- System-wide AI assistance
- Inter-process communication
- Desktop application integration

#### Starting the D-Bus Server

```bash
# Using the main launcher (recommended)
python main.py
# Select option 1

# Or directly
python dbus_server.py
```

### Web Server (HTTP REST API)

RIGEL's web server provides a REST API interface accessible from any HTTP client, with automatic OpenAPI documentation.

**Best for:**
- Cross-platform compatibility
- Remote access
- Web applications
- Mobile app backends
- API integrations

#### Starting the Web Server

```bash
# Using the main launcher (recommended)
python main.py
# Select option 2

# Or directly
python web_server.py
```

The web server will be available at:
- **Main API**: http://localhost:8000
- **Interactive Documentation**: http://localhost:8000/docs
- **OpenAPI Schema**: http://localhost:8000/openapi.json

#### Web Server Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Service information |
| `/query` | POST | Basic inference |
| `/query-with-memory` | POST | Inference with conversation memory |
| `/query-think` | POST | Advanced thinking capabilities |
| `/query-with-tools` | POST | Inference with MCP tools support |
| `/synthesize-text` | POST | Convert text to speech |
| `/recognize-audio` | POST | Transcribe audio file to text |
| `/license-info` | GET | License and copyright information |

#### Web API Usage Examples

```bash
# Basic query
curl -X POST "http://localhost:8000/query" \
     -H "Content-Type: application/json" \
     -d '{"query": "Hello RIGEL!"}'

# Query with memory
curl -X POST "http://localhost:8000/query-with-memory" \
     -H "Content-Type: application/json" \
     -d '{"query": "My name is Alice", "id": "user123"}'

# Query with tools
curl -X POST "http://localhost:8000/query-with-tools" \
     -H "Content-Type: application/json" \
     -d '{"query": "What time is it and list files in current directory?"}'

# Text synthesis
curl -X POST "http://localhost:8000/synthesize-text" \
     -H "Content-Type: application/json" \
     -d '{"text": "Hello, this is RIGEL speaking!", "mode": "chunk"}'

# Audio recognition
curl -X POST "http://localhost:8000/recognize-audio" \
     -F "audio_file=@audio.wav" \
     -F "model=tiny"
```

Both servers support the same core functionality but with different interfaces. Choose the one that best fits your use case.

#### Starting the MCP Server on a separate instance

For debugging or standalone use, you can start the built-in MCP server manually:

```bash
cd core/mcp/
python rigel_tools_server.py
```

#### Configuring MCP Servers

Before starting the D-Bus server, you can configure custom MCP servers by editing `server.py`. The file includes commented examples showing how to:

- Configure the built-in "rigel tools" server (SSE transport)
- Add external MCP servers like "python-toolbox" (STDIO transport)
- Set up environment variables and command-line arguments

To enable MCP functionality:

1. **Edit `server.py`** and uncomment the `default_mcp` configuration
2. **Modify paths and settings** to match your environment
3. **Start any external MCP servers** if using STDIO transport
4. **Run the RIGEL server** with your MCP configuration

If no MCP servers are configured, RIGEL will display a helpful message with setup instructions.

#### Using the D-Bus Service

```python
from pydbus import SessionBus

bus = SessionBus()
service = bus.get("com.rigel.RigelService")

# Basic query
response = service.Query("Hello RIGEL!")
print(response)

# Query with memory (remembers conversation context)
response = service.QueryWithMemory("My name is Alice", "user123")
follow_up = service.QueryWithMemory("What's my name?", "user123")

# Advanced thinking capabilities
response = service.QueryThink("How should I approach solving this complex problem?")

# Query with MCP tools (file operations, system commands, etc.)
response = service.QueryWithTools("What time is it and list the files in the current directory?")
response = service.QueryWithTools("Read the README.md file and summarize its contents")
response = service.QueryWithTools("Check the system uptime and current user")

# Voice synthesis and recognition
response = service.SynthesizeText("Hello, this is RIGEL speaking!", "chunk")
transcription = service.RecognizeAudio("/path/to/audio.wav", "tiny")
```

## Voice Features

RIGEL includes comprehensive voice capabilities for both speech synthesis and recognition, enabling natural voice interactions with your AI assistant.

### Voice Synthesis (Text-to-Speech)

RIGEL uses Piper TTS for high-quality, local voice synthesis with multiple modes:

#### Synthesis Modes

- **Chunk Mode**: Processes text in chunks (sentences) for streaming audio playback
- **Linear Mode**: Processes entire text as a single unit

#### Using Voice Synthesis

```python
from pydbus import SessionBus

bus = SessionBus()
service = bus.get("com.rigel.RigelService")

# Chunk mode for streaming (recommended for longer texts)
result = service.SynthesizeText("Hello, this is RIGEL speaking. I can help you with various tasks.", "chunk")

# Linear mode for simple, quick synthesis
result = service.SynthesizeText("Welcome to RIGEL!", "linear")
```

#### Direct Python Usage

```python
from core.synth_n_recog import Synthesizer

# Initialize synthesizer
synthesizer = Synthesizer(mode="chunk")

# Synthesize and play text
synthesizer.synthesize("Hello, this is RIGEL speaking!")

# Switch modes
synthesizer.mode = "linear"
synthesizer.synthesize("Quick announcement!")
```

### Voice Recognition (Speech-to-Text)

RIGEL uses OpenAI Whisper for accurate, local speech recognition supporting multiple model sizes:

#### Available Models

- **tiny**: Fastest, good for real-time processing
- **base**: Balanced speed and accuracy
- **small**: Better accuracy, slower processing
- **medium**: High accuracy for most use cases
- **large**: Best accuracy, slowest processing

#### Using Voice Recognition

```python
from pydbus import SessionBus

bus = SessionBus()
service = bus.get("com.rigel.RigelService")

# Transcribe audio file
transcription = service.RecognizeAudio("/path/to/audio.wav", "tiny")
print(f"Transcription: {transcription}")

# Use different model for better accuracy
transcription = service.RecognizeAudio("/path/to/audio.wav", "base")
```

#### Direct Python Usage

```python
from core.synth_n_recog import Recognizer

# Initialize recognizer with desired model
recognizer = Recognizer(model="tiny")

# Transcribe audio file
transcription = recognizer.transcribe("/path/to/audio.wav")
print(f"Transcription: {transcription}")
```

### Voice Requirements

#### System Dependencies

```bash
# Install Piper TTS
# Download from: https://github.com/rhasspy/piper/releases
# Ensure 'piper' command is available in PATH

# Install PulseAudio for audio playback
sudo apt-get install pulseaudio pulseaudio-utils  # Ubuntu/Debian
sudo dnf install pulseaudio pulseaudio-utils      # Fedora/RHEL
```

#### Python Dependencies

Voice features require additional dependencies included in `requirements.txt`:
- `openai-whisper`: For speech recognition
- `torch`, `torchaudio`, `torchvision`: PyTorch dependencies for Whisper

#### Voice Models

- **Piper Model**: `jarvis-medium.onnx` (included in `core/synthesis_assets/`)
- **Whisper Models**: Downloaded automatically when first used

### D-Bus Voice Endpoints

#### `SynthesizeText(text: str, mode: str) -> str`
- **Description**: Converts text to speech with specified synthesis mode
- **Parameters**: 
  - `text` - The text to synthesize
  - `mode` - Synthesis mode: "chunk" or "linear"
- **Returns**: Status message indicating synthesis started
- **Use Case**: Voice output for AI responses, notifications, accessibility

#### `RecognizeAudio(audio_file_path: str, model: str) -> str`
- **Description**: Transcribes audio file to text using Whisper
- **Parameters**:
  - `audio_file_path` - Path to audio file (WAV, MP3, etc.)
  - `model` - Whisper model size: "tiny", "base", "small", "medium", "large"
- **Returns**: Transcribed text from audio
- **Use Case**: Voice input processing, audio transcription, accessibility

### Basic Usage with Ollama

```python
from core.rigel import RigelOllama

# Initialize RIGEL with Ollama backend
rigel = RigelOllama(model_name="llama3.2")

# Define your messages
messages = [
    ("system", "You are RIGEL, a helpful assistant"),
    ("human", "Hello! How can you help me today?"),
]

# Get response
response = rigel.inference(messages=messages)
print(response.content)
```

### Basic Usage with Groq

```python
from core.rigel import RigelGroq
import os

# Set your Groq API key
os.environ["GROQ_API_KEY"] = "your-groq-api-key-here"

# Initialize RIGEL with Groq backend
rigel = RigelGroq(model_name="llama3-70b-8192")

# Define your messages
messages = [
    ("system", "You are RIGEL, a helpful assistant"),
    ("human", "What's the weather like today?"),
]

# Get response
response = rigel.inference(messages=messages)
print(response.content)
```

### Usage with Memory

```python
from core.rigel import RigelOllama

# Initialize RIGEL with Ollama backend
rigel = RigelOllama(model_name="llama3.2")

# Define your messages with memory support
messages = [
    ("human", "My name is John. Remember this!"),
]

# Get response with memory
response = rigel.inference_with_memory(messages=messages, thread_id="conversation1")
print(response.content)

# Continue conversation - RIGEL will remember previous context
follow_up = [
    ("human", "What's my name?"),
]

response2 = rigel.inference_with_memory(messages=follow_up, thread_id="conversation1")
print(response2.content)  # Should remember the name is John

# Get conversation history
history = rigel.get_conversation_history(thread_id="conversation1")
print(f"Conversation has {len(history)} messages")

# Clear memory when needed
rigel.clear_memory(thread_id="conversation1")
```

## Project Structure

```
RIGEL_SERVICE/
├── core/
│   ├── rigel.py          # Main RIGEL engine classes
│   ├── logger.py         # Logging utilities
│   ├── rdb.py            # RAG database functionality
│   ├── synth_n_recog.py  # Voice synthesis and recognition
│   ├── mcp/              # MCP (Model Context Protocol) tools
│   │   └── rigel_tools_server.py  # MCP server implementation
│   ├── synthesis_assets/ # Voice synthesis models
│   │   ├── jarvis-medium.onnx     # Piper TTS model
│   │   └── jarvis-medium.onnx.json # Model configuration
│   └── *.log             # Log files
├── server.py             # D-Bus server implementation
├── demo_client.py        # Example D-Bus client with voice features
├── test_voice_features.py # Voice features test suite
├── requirements.txt      # Python dependencies
├── README.md            # This file
├── CHANGELOG.md         # Version history and changes
├── VOICE_SETUP.md       # Voice features setup guide
├── LICENSE              # AGPL-3.0 license
├── Prototyping/          # Experimental features
├── Research/             # Research and documentation
│   ├── client.py         # Example D-Bus client
│   └── dbus_test.py      # D-Bus testing utilities
└── assets/              # Project assets
    ├── rigel_logo.png    # RIGEL logo
    └── RIGEL_No_text.svg # RIGEL logo without text
```

## API Reference

### Core Classes

#### `Rigel` (Base Class)
The superclass for all RIGEL implementations.

**Methods:**
- `inference(messages: list, model: str = None)` - Perform inference with given messages
- `inference_with_memory(messages: list, model: str = None, thread_id: str = "default")` - Perform inference with conversation memory
- `get_conversation_history(thread_id: str = "default")` - Retrieve conversation history for a thread
- `clear_memory(thread_id: str = "default")` - Clear memory for a specific conversation thread
- `think(think_message, model: str = None)` - Advanced thinking capabilities
- `decision(decision_message, model: str = None)` - [TODO] Decision-making capabilities

#### `RigelOllama`
RIGEL implementation using Ollama backend.

**Constructor:**
- `RigelOllama(model_name: str = "llama3.2")`

#### `RigelGroq`
RIGEL implementation using Groq backend.

**Constructor:**
- `RigelGroq(model_name: str = "llama3-70b-8192", temp: float = 0.7)`

#### `Synthesizer`
Voice synthesis class for text-to-speech conversion.

**Constructor:**
- `Synthesizer(mode: str = "chunk")`

**Methods:**
- `synthesize(text: str)` - Convert text to speech and play audio

**Modes:**
- `chunk` - Process text in sentence chunks for streaming playback
- `linear` - Process entire text as single unit

#### `Recognizer`
Voice recognition class for speech-to-text conversion.

**Constructor:**
- `Recognizer(model: str = "tiny")`

**Methods:**
- `transcribe(file_path: str) -> str` - Transcribe audio file to text

**Models:**
- `tiny`, `base`, `small`, `medium`, `large` - Whisper model sizes

## Message Format

Messages should be provided as a list of tuples in the following format:

```python
messages = [
    ("system", "System prompt here"),
    ("human", "User message here"),
    ("assistant", "Assistant response here"),  # Optional
]
```

## RAG (Retrieval-Augmented Generation)

RIGEL includes basic RAG functionality using ChromaDB:

### Using RAG

```python
from core.rdb import DBConn

# Initialize database connection
db = DBConn()

# Load data from PDF
db.load_data_from_pdf_path("path/to/document.pdf")

# Load data from text file
db.load_data_from_txt_path("path/to/document.txt")

# Perform similarity search
results = db.run_similar_serch("your search query")
print(results)
```

## MCP (Model Context Protocol) Tools

RIGEL includes comprehensive MCP support that significantly extends the AI's capabilities with real-world system operations. The MCP server provides a secure bridge between the AI and your system, enabling file operations, command execution, and system information retrieval.

### Key MCP Capabilities

#### 🛠️ System Operations
- **Real-time Information**: Get current time, system information, and user environment details
- **Command Execution**: Safely execute shell commands with output capture
- **Process Management**: Monitor and interact with system processes

#### 📁 File Management
- **File I/O**: Read from and write to any accessible file on the system
- **Directory Navigation**: List and explore directory structures
- **Content Analysis**: AI can analyze file contents and provide insights

#### 🔧 Advanced Features
- **Secure Execution**: All operations run within controlled boundaries
- **Error Handling**: Robust error reporting and recovery mechanisms
- **Real-time Integration**: Seamless integration with AI reasoning

### MCP Server Configuration

RIGEL supports multiple MCP servers through the `MultiServerMCPClient`. You can configure custom MCP servers in `server.py` before initialization.

#### Built-in MCP Server

RIGEL includes a built-in MCP server with essential system tools:

```bash
# Start the built-in MCP server manually (for debugging)
python core/mcp/rigel_tools_server.py
```

#### Configuring Custom MCP Servers

To add custom MCP servers, edit the `server.py` file and uncomment/modify the MCP configuration:

```python
# Example MCP server configuration in server.py
default_mcp = MultiServerMCPClient(
    {
        "rigel tools": {
            "url": "http://localhost:8001/sse",
            "transport": "sse",
        },
        "python-toolbox": {
            "command": "/path/to/your/mcp_server/.venv/bin/python",
            "args": [
                "-m",
                "mcp_server_package",
                "--workspace",
                "/path/to/workspace"
            ],
            "env": {
                "PYTHONPATH": "/path/to/your/mcp_server/src",
                "PATH": "/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
                "VIRTUAL_ENV": "/path/to/your/mcp_server/.venv",
                "PYTHONHOME": ""
            },
            "transport": "stdio"
        }
    },
)
```

#### MCP Transport Types

RIGEL supports two MCP transport methods:

- **SSE (Server-Sent Events)**: For HTTP-based MCP servers
  ```python
  "transport": "sse",
  "url": "http://localhost:8001/sse"
  ```

- **STDIO**: For process-based MCP servers
  ```python
  "transport": "stdio",
  "command": "/path/to/executable",
  "args": ["arg1", "arg2"]
  ```

#### MCP Server Network Configuration

The built-in MCP server runs on **port 8001** by default using Server-Sent Events (SSE) transport:

```python
# Default configuration in server.py
"rigel tools": {
    "url": "http://localhost:8001/sse",
    "transport": "sse",
}
```

To change the port, modify both:
1. **`core/mcp/rigel_tools_server.py`**: Update the `port=8001` parameter in `FastMCP()`
2. **`server.py`**: Update the URL in the MCP client configuration

#### Adding Your Own MCP Server

1. **Create your MCP server** following the MCP specification
2. **Edit `server.py`** and add your server to the `MultiServerMCPClient` configuration
3. **Set `default_mcp`** to your configuration instead of `None`
4. **Restart the RIGEL service** to load the new configuration

If no MCP servers are configured (`default_mcp = None`), RIGEL will display a warning message suggesting you configure MCP servers for enhanced functionality.

#### MCP Troubleshooting

**Common Issues:**

1. **"MCP server connection failed"**
   - Ensure the MCP server is running before starting RIGEL
   - Check that port 8001 is available and not blocked by firewall
   - Verify the URL in the configuration matches the server

2. **"QueryWithTools times out"**
   - Commands have a 30-second timeout for safety
   - Check if the requested operation is resource-intensive
   - Verify system commands are valid and accessible

3. **"Permission denied" errors**
   - MCP tools respect system file permissions
   - Ensure RIGEL has appropriate access to requested files/directories
   - Check user permissions for system commands

4. **MCP tools not available**
   - Verify `default_mcp` is properly configured in `server.py`
   - Ensure MCP dependencies are installed: `pip install langchain_mcp_adapters`
   - Check that the MCP server started successfully

### Available MCP Tools

The built-in RIGEL MCP server (`core/mcp/rigel_tools_server.py`) provides the following tools:

#### System Operations
- **`current_time()`** - Get current system date and time in YYYY-MM-DD HH:MM:SS format
- **`get_system_info()`** - Retrieve comprehensive system information including:
  - Current working directory
  - Current user name
  - Home directory path
  - Default shell
  - Python version
- **`run_system_command(command)`** - Execute shell commands safely with output capture
  - 30-second timeout for safety
  - Returns both stdout and stderr
  - Captures exit codes for error handling

#### File Operations
- **`read_file(file_path)`** - Read contents of any accessible file
  - Supports UTF-8 encoding
  - Returns full file contents or error message
- **`write_file(file_path, content)`** - Write content to files
  - Creates files if they don't exist
  - UTF-8 encoding support
  - Returns success confirmation or error details
- **`list_directory(directory_path=".")`** - List directory contents with visual indicators
  - 📁 for directories (with trailing slash)
  - 📄 for files
  - Defaults to current directory if no path provided
  - Sorted alphabetically for consistent output

#### Tool Safety Features
- **Timeout Protection**: Commands have built-in 30-second timeouts
- **Error Handling**: Comprehensive error messages for debugging
- **Encoding Support**: UTF-8 support for international characters
- **Permission Respect**: All operations respect system file permissions

### MCP Usage Examples

#### Through D-Bus Service (Recommended)

```python
from pydbus import SessionBus

bus = SessionBus()
service = bus.get("com.rigel.RigelService")

# System information and time
response = service.QueryWithTools("What time is it and what system am I running on?")

# File operations
response = service.QueryWithTools("Read the README.md file and give me a brief summary")

# Directory exploration with visual indicators
response = service.QueryWithTools("List all files in the current directory and show me their types")

# System commands with timeout protection
response = service.QueryWithTools("Check disk usage with 'df -h' and show system uptime")

# Combined operations
response = service.QueryWithTools(
    "Get the current time, list Python files in the current directory, and check who I am"
)

# File creation and management
response = service.QueryWithTools("Create a test file called 'hello.txt' with 'Hello World' content")

# Advanced system analysis
response = service.QueryWithTools(
    "Show me system information, current directory contents, and check if Python is installed"
)
```

#### Direct Python Usage

```python
from core.rigel import RigelOllama

# Initialize RIGEL with MCP support
rigel = RigelOllama(model_name="llama3.2")

# Define messages that require tool usage
messages = [
    ("system", "You are RIGEL with access to system tools. Use them when appropriate."),
    ("human", "What time is it and what files are in the current directory?"),
]

# Use inference_with_tools method (if available)
response = rigel.inference(messages=messages)
print(response.content)
```

### MCP Setup Instructions

When you first run RIGEL without MCP server configuration, you'll see this message:

```
Open server.py and add your custom mcp servers here before initializing
There is a basic mcp server built in inside core/mcp/rigel_tools_server.py
You can start it by typing 
python core/mcp/rigel_tools_server.py
```

To set up MCP functionality:

1. **For basic functionality**: Start the built-in MCP server in a separate terminal:
   ```bash
   python core/mcp/rigel_tools_server.py
   ```

2. **For advanced functionality**: Edit `server.py` to configure multiple MCP servers:
   - Uncomment the `default_mcp = MultiServerMCPClient(...)` section
   - Modify server configurations to match your setup
   - Add additional MCP servers as needed

3. **Restart RIGEL** to load the new MCP configuration

#### MCP Security Notes

- All file operations respect system permissions
- Commands are executed in a controlled environment
- Sensitive operations require explicit user intent
- Error handling prevents system damage

## D-Bus Server

RIGEL's D-Bus server provides a powerful system-wide interface for AI assistance, complete with advanced tool capabilities and memory management.

### D-Bus Interface Details

- **Service Name**: `com.rigel.RigelService`
- **Interface**: `com.rigel.RigelService`
- **Object Path**: `/com/rigel/RigelService`

### Available D-Bus Endpoints

#### Core Inference Endpoints

- **`Query(query: str) -> str`**
  - **Description**: Performs basic inference with the configured backend
  - **Parameters**: `query` - The user's message/question
  - **Returns**: AI response as string
  - **Use Case**: Simple AI interactions without memory or tools
  - **Example**: 
    ```python
    response = service.Query("What is artificial intelligence?")
    ```

- **`QueryWithMemory(query: str, thread_id: str) -> str`**
  - **Description**: Performs inference with persistent conversation memory
  - **Parameters**: 
    - `query` - The user's message/question
    - `thread_id` - Unique identifier for conversation thread
  - **Returns**: AI response as string with full context awareness
  - **Use Case**: Multi-turn conversations with context retention
  - **Example**:
    ```python
    response = service.QueryWithMemory("My name is Alice and I'm a developer", "user123")
    follow_up = service.QueryWithMemory("What do you know about me?", "user123")
    ```

- **`QueryThink(query: str) -> str`**
  - **Description**: Performs advanced thinking/reasoning operations
  - **Parameters**: `query` - The problem or scenario requiring deep thought
  - **Returns**: AI reasoning response with detailed analysis
  - **Use Case**: Complex problem solving, analysis, and decision making
  - **Example**:
    ```python
    response = service.QueryThink("I need to choose between two job offers. Help me think through this decision.")
    ```

- **`QueryWithTools(query: str) -> str`**
  - **Description**: Performs inference with full MCP (Model Context Protocol) tools support
  - **Parameters**: `query` - The user's message/question that may require system operations
  - **Returns**: AI response with tool execution results integrated
  - **Use Case**: System administration, file management, real-time information
  - **Available Tools**:
    - `current_time()` - Get current date and time
    - `run_system_command(command)` - Execute shell commands
    - `read_file(path)` - Read file contents
    - `write_file(path, content)` - Write content to files
    - `list_directory(path)` - List directory contents
    - `get_system_info()` - Get comprehensive system information
  - **Example**:
    ```python
    response = service.QueryWithTools("What time is it?")
    response = service.QueryWithTools("List files in the current directory and read the README")
    response = service.QueryWithTools("Check system load and create a status report")
    ```

### Running the D-Bus Server

#### Using the Main Launcher (Recommended)

```bash
python main.py
```

Select option 1 for D-Bus server. The launcher will check dependencies and provide helpful setup instructions if needed.

#### Direct Launch

```bash
python dbus_server.py
```

The server will prompt you to choose between:
1. **Groq** (Cloud-based, high performance)
2. **Ollama** (Local, privacy-focused)

### D-Bus Client Examples

#### Basic Client Setup

```python
from pydbus import SessionBus

bus = SessionBus()
service = bus.get("com.rigel.RigelService")
```

#### Advanced Usage Patterns

```python
# Multi-modal conversation with memory
thread_id = "project_discussion"
service.QueryWithMemory("I'm working on a Python web scraping project", thread_id)
service.QueryWithMemory("What libraries should I use?", thread_id)
service.QueryWithMemory("Show me the project structure", thread_id)

# System administration with tools
service.QueryWithTools("Check system health: CPU, memory, disk usage")
service.QueryWithTools("List all Python projects in my home directory")
service.QueryWithTools("Create a backup script for my important files")

# Complex reasoning
service.QueryThink("Analyze the pros and cons of microservices vs monolithic architecture")
```

## Web Server

RIGEL's web server provides a modern REST API interface with automatic OpenAPI documentation, making it easy to integrate RIGEL into web applications, mobile apps, and other HTTP-based systems.

### Web API Endpoints

The web server provides the same functionality as the D-Bus server through HTTP endpoints:

| Endpoint | Method | Description | Request Body |
|----------|--------|-------------|--------------|
| `/` | GET | Service information and available endpoints | None |
| `/query` | POST | Basic inference | `{"query": "string"}` |
| `/query-with-memory` | POST | Inference with conversation memory | `{"query": "string", "id": "string"}` |
| `/query-think` | POST | Advanced thinking capabilities | `{"query": "string"}` |
| `/query-with-tools` | POST | Inference with MCP tools support | `{"query": "string"}` |
| `/synthesize-text` | POST | Convert text to speech | `{"text": "string", "mode": "chunk/linear"}` |
| `/recognize-audio` | POST | Transcribe audio file to text | Multipart form with `audio_file` and `model` |
| `/license-info` | GET | License and copyright information | None |

### Running the Web Server

#### Using the Main Launcher (Recommended)

```bash
python main.py
```

Select option 2 for Web server. The launcher will check dependencies and provide setup instructions if needed.

#### Direct Launch

```bash
python web_server.py
```

The server will start on `http://localhost:8000` with the following URLs available:
- **Main API**: http://localhost:8000
- **Interactive Documentation**: http://localhost:8000/docs
- **OpenAPI Schema**: http://localhost:8000/openapi.json

### Web API Usage Examples

#### Using curl

```bash
# Service information
curl http://localhost:8000/

# Basic query
curl -X POST "http://localhost:8000/query" \
     -H "Content-Type: application/json" \
     -d '{"query": "Hello RIGEL! Tell me about artificial intelligence."}'

# Query with memory - start conversation
curl -X POST "http://localhost:8000/query-with-memory" \
     -H "Content-Type: application/json" \
     -d '{"query": "My name is Alice and I am a software developer", "id": "user123"}'

# Query with memory - continue conversation
curl -X POST "http://localhost:8000/query-with-memory" \
     -H "Content-Type: application/json" \
     -d '{"query": "What do you know about me?", "id": "user123"}'

# Advanced thinking
curl -X POST "http://localhost:8000/query-think" \
     -H "Content-Type: application/json" \
     -d '{"query": "I need to choose between two job offers. One pays more but has worse work-life balance. Help me think through this decision."}'

# Query with tools
curl -X POST "http://localhost:8000/query-with-tools" \
     -H "Content-Type: application/json" \
     -d '{"query": "What time is it? Also, list the files in the current directory and summarize any README files you find."}'

# Text synthesis
curl -X POST "http://localhost:8000/synthesize-text" \
     -H "Content-Type: application/json" \
     -d '{"text": "Hello, this is RIGEL speaking! I am now available via web API.", "mode": "chunk"}'

# Audio recognition
curl -X POST "http://localhost:8000/recognize-audio" \
     -F "audio_file=@path/to/audio.wav" \
     -F "model=tiny"

# License information
curl http://localhost:8000/license-info
```

#### Using Python requests

```python
import requests
import json

# Base URL
base_url = "http://localhost:8000"

# Basic query
response = requests.post(
    f"{base_url}/query",
    json={"query": "What is machine learning?"}
)
print(response.json())

# Query with memory
response = requests.post(
    f"{base_url}/query-with-memory",
    json={
        "query": "Remember that I am working on a Python project",
        "id": "session_001"
    }
)
print(response.json())

# Follow up with memory
response = requests.post(
    f"{base_url}/query-with-memory",
    json={
        "query": "What programming language am I using?",
        "id": "session_001"
    }
)
print(response.json())

# Query with tools
response = requests.post(
    f"{base_url}/query-with-tools",
    json={"query": "Check system information and current time"}
)
print(response.json())

# Text synthesis
response = requests.post(
    f"{base_url}/synthesize-text",
    json={
        "text": "This is a test of the voice synthesis system",
        "mode": "chunk"
    }
)
print(response.json())

# Audio recognition
with open("audio.wav", "rb") as audio_file:
    response = requests.post(
        f"{base_url}/recognize-audio",
        files={"audio_file": audio_file},
        data={"model": "tiny"}
    )
print(response.json())
```

#### Using JavaScript/Node.js

```javascript
const axios = require('axios');

const baseURL = 'http://localhost:8000';

// Basic query
async function basicQuery() {
    try {
        const response = await axios.post(`${baseURL}/query`, {
            query: "Explain quantum computing in simple terms"
        });
        console.log(response.data);
    } catch (error) {
        console.error('Error:', error.response.data);
    }
}

// Query with memory
async function queryWithMemory() {
    try {
        // Start conversation
        let response = await axios.post(`${baseURL}/query-with-memory`, {
            query: "I'm learning web development with React",
            id: "webdev_session"
        });
        console.log('First response:', response.data);

        // Continue conversation
        response = await axios.post(`${baseURL}/query-with-memory`, {
            query: "What should I learn next?",
            id: "webdev_session"
        });
        console.log('Follow-up response:', response.data);
    } catch (error) {
        console.error('Error:', error.response.data);
    }
}

// Query with tools
async function queryWithTools() {
    try {
        const response = await axios.post(`${baseURL}/query-with-tools`, {
            query: "What's the current time and what files are in this directory?"
        });
        console.log(response.data);
    } catch (error) {
        console.error('Error:', error.response.data);
    }
}

// Run examples
basicQuery();
queryWithMemory();
queryWithTools();
```

The web server provides the same powerful AI capabilities as the D-Bus interface but with the flexibility and accessibility of HTTP/REST APIs, making it perfect for web applications, mobile apps, and cross-platform integrations.

## Environment Variables

- `GROQ_API_KEY`: Required for Groq backend usage

## Logging

RIGEL includes comprehensive logging capabilities. Logs are written to:
- `core/rigel.log` - Main application logs
- `core/syslog.log` - System logs

Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the GNU Affero General Public License v3.0 (AGPL-3.0).

This means you can:
- Use the software for any purpose
- Study and modify the source code
- Share copies of the software
- Share modified versions

However, if you run a modified version on a server and provide network services, you must also provide the source code of your modifications to users of that service.

See the [LICENSE](LICENSE) file for the full license text.

## Support

For support, please open an issue in the GitHub repository or contact Zerone Laboratories.

### Additional Documentation

- **[Voice Setup Guide](VOICE_SETUP.md)** - Complete guide for setting up voice features
- **[Changelog](CHANGELOG.md)** - Version history and new features
- **[License](LICENSE)** - Full AGPL-3.0 license text

## Keywords & Topics

**AI Assistant** • **Virtual Assistant** • **Multi-LLM** • **Agentic AI** • **Ollama** • **Groq** • **Python AI Framework** • **Open Source AI** • **Local AI** • **Cloud AI** • **D-Bus** • **MCP Tools** • **AI Inference Engine** • **Chatbot Framework** • **LLM Backend** • **AI Memory** • **RAG** • **LLAMA** • **Transformers** • **Voice Recognition** • **Speech Synthesis** • **TTS** • **STT** • **Whisper** • **Piper** • **AI Development** • **Machine Learning** • **Natural Language Processing** • **Conversational AI** • **AI Tools** • **System Integration**

---

An effort to make it easier for the opensource community to build your own Virtual Assistant.

**Zerone Laboratories Systems - RIGEL Engine v4.0.X[Dev]** 