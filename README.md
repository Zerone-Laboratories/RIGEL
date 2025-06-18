# RIGEL

<div align="center">
  <img src="assets/rigel_logo.png" alt="RIGEL Logo" width="300"/>
</div>

> Rigel Engine v4.0

An opensource Agentic Assistant with multi-backend LLM support, designed for flexible AI inference and decision-making capabilities.

## Overview

RIGEL is a powerful multi-agentic engine that provides a unified interface for multiple language model backends. Built with extensibility in mind, it supports both local inference via Ollama and cloud-based inference through Groq. Aims to act as a central server for multiple 
Agentic based clients


## Project Status

| Feature | Status |
|---------|--------|
| Inference with Ollama | ✓ |
| Inference with Groq | ✓ |
| Thinking | ✓ |
| MCP | - |
| Dbus Server | Partial |
| RAG | Partial |
| Memory | ✓ |


## Features

- **Multi-Backend Support**: Seamlessly switch between Ollama (local) and Groq (cloud) backends. More backends will be integrated in future
- **Extensible Architecture**: Built with a superclass design for easy extension to new capabilities
- **Comprehensive Logging**: Integrated logging system for debugging and monitoring
- **Flexible Inference**: Support for custom prompts and message formats
- **Future-Ready**: Designed for upcoming features like vision, MCP (Model Context Protocol), and advanced thinking capabilities

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
cd RIGEL_SERVICE
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

4. For Ollama backend, ensure Ollama is installed and running:
```bash
# Install Ollama (if not already installed)
curl -fsSL https://ollama.ai/install.sh | sh

# Pull the default model
ollama pull llama3.2
```

5. For D-Bus functionality (Linux only), ensure system dependencies:
```bash
# Ubuntu/Debian
sudo apt-get install python3-gi python3-gi-cairo gir1.2-gtk-3.0

# Fedora/RHEL
sudo dnf install python3-gobject python3-gobject-cairo gtk3-devel
```

## Quick Start

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
│   └── *.log             # Log files
├── server.py             # D-Bus server implementation
├── requirements.txt      # Python dependencies
├── Prototyping/          # Experimental features
├── Research/             # Research and documentation
│   ├── client.py         # Example D-Bus client
│   └── dbus_test.py      # D-Bus testing utilities
└── README.md            # This file
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

## D-Bus Server

RIGEL includes a D-Bus server implementation for inter-process communication:

### Running the D-Bus Server

```bash
python server.py
```

The server will prompt you to choose between Groq (1) or Ollama (2) backend.

### D-Bus Interface Details

- **Service Name**: `com.rigel.RigelService`
- **Interface**: `com.rigel.RigelService`
- **Method**: `Query(query: str) -> str`

### Using the D-Bus Client

```python
from pydbus import SessionBus

bus = SessionBus()
service = bus.get("com.rigel.RigelService")

response = service.Query("Hello RIGEL!")
print(response)
```

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

This project is open source. Please check the LICENSE file for details.

## Support

For support, please open an issue in the GitHub repository or contact Zerone Laboratories.

---

**Zerone Laboratories Systems - RIGEL Engine v4.0[Alpha]** 