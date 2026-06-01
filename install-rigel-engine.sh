#!/usr/bin/env bash
set -Eeuo pipefail

# ─── RIGEL Engine Installer ──────────────────────────────────────────────────
# Installs RIGEL as a system D-Bus service with Docker
# Usage: curl -fsSL https://.../install.sh | sudo bash
#    or: sudo ./install-rigel-engine.sh
# ──────────────────────────────────────────────────────────────────────────────

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

REPO_URL="https://github.com/Zerone-Laboratories/RIGEL.git"
INSTALL_DIR="/opt/rigel-engine"
DBUS_CONF_FILE="rigel-dbus.conf"
DBUS_SERVICE_NAME="com.rigel.RigelService"

banner() {
    echo -e "${CYAN}"
    echo "  ╔══════════════════════════════════════════╗"
    echo "  ║  ██████╗ ██╗ ██████╗ ███████╗██╗        ║"
    echo "  ║  ██╔══██╗██║██╔════╝ ██╔════╝██║        ║"
    echo "  ║  ██████╔╝██║██║  ███╗█████╗  ██║        ║"
    echo "  ║  ██╔══██╗██║██║   ██║██╔══╝  ██║        ║"
    echo "  ║  ██║  ██║██║╚██████╔╝███████╗███████╗   ║"
    echo "  ║  ╚═╝  ╚═╝╚═╝ ╚═════╝ ╚══════╝╚══════╝   ║"
    echo "  ║          Engine Installer v1.0           ║"
    echo "  ╚══════════════════════════════════════════╝"
    echo -e "${NC}"
}

info()  { echo -e "${GREEN}[✓]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
err()   { echo -e "${RED}[✗]${NC} $*" >&2; }
step()  { echo -e "\n${BOLD}${CYAN}▶ $*${NC}"; }
detail(){ echo -e "  ${CYAN}→${NC} $*"; }

# Prevent double-banner on re-exec by tracking via env var
_RIGEL_ELEVATED="${_RIGEL_ELEVATED:-0}"

require_root() {
    if [[ $EUID -ne 0 ]]; then
        warn "This installer needs root privileges. Elevating with sudo..."
        local script_path="${BASH_SOURCE[0]:-$0}"
        if command -v realpath &>/dev/null; then
            script_path="$(realpath "$script_path" 2>/dev/null || echo "$script_path")"
        fi

        # In `curl ... | bash` mode, $0 can be "bash" (not a real file path).
        # Re-exec only when we have a readable script file; otherwise fail with
        # an explicit rerun instruction.
        if [[ -f "$script_path" && -r "$script_path" ]]; then
            exec sudo -E _RIGEL_ELEVATED=1 bash "$script_path" "$@"
        fi

        err "Cannot auto-elevate when the installer is piped via stdin."
        echo "  Re-run with sudo on the bash invocation:"
        echo "  curl -fsSL https://raw.githubusercontent.com/Zerone-Laboratories/RIGEL/main/install-rigel-engine.sh | sudo -E bash"
        exit 1
    fi
}

check_docker() {
    step "Checking Docker installation..."
    if ! command -v docker &>/dev/null; then
        err "Docker is not installed."
        echo ""
        echo "  Please install Docker first:"
        echo "    https://docs.docker.com/engine/install/"
        echo ""
        echo "  Quick install (Debian/Ubuntu):"
        echo "    sudo apt update && sudo apt install docker.io docker-compose-v2"
        echo ""
        echo "  Quick install (Arch):"
        echo "    sudo pacman -S docker docker-compose"
        echo ""
        echo "  After installing, enable and start the Docker service:"
        echo "    sudo systemctl enable --now docker"
        echo ""
        exit 1
    fi

    if ! docker info &>/dev/null; then
        err "Docker is installed but the daemon is not running or accessible."
        echo "  Start it with: sudo systemctl start docker"
        exit 1
    fi

    DOCKER_VERSION=$(docker --version 2>/dev/null | head -1)
    info "Docker detected: $DOCKER_VERSION"
}

check_dbus() {
    step "Checking D-Bus system service..."
    if ! command -v dbus-daemon &>/dev/null && ! systemctl is-active --quiet dbus 2>/dev/null; then
        warn "D-Bus daemon not detected. RIGEL uses D-Bus for system integration."
        warn "Install dbus if needed: sudo apt install dbus (Debian/Ubuntu) or sudo pacman -S dbus (Arch)"
    else
        info "D-Bus system service is available"
    fi
}

install_dbus_config() {
    step "Installing RIGEL D-Bus system configuration..."
    mkdir -p /etc/dbus-1/system.d/
    cp "$INSTALL_DIR/$DBUS_CONF_FILE" /etc/dbus-1/system.d/
    chmod 644 "/etc/dbus-1/system.d/$DBUS_CONF_FILE"

    if command -v systemctl &>/dev/null; then
        if systemctl is-active --quiet dbus 2>/dev/null; then
            systemctl reload dbus 2>/dev/null || true
            info "D-Bus configuration installed and reloaded"
        else
            info "D-Bus configuration installed (dbus service not running, will apply on start)"
        fi
    else
        warn "systemctl not found — reload D-Bus manually: kill -HUP \$(pidof dbus-daemon)"
    fi
}

clone_repo() {
    step "Setting up RIGEL engine at $INSTALL_DIR..."

    if [[ -d "$INSTALL_DIR/.git" ]]; then
        info "Existing installation found. Updating..."
        cd "$INSTALL_DIR"
        git fetch origin 2>/dev/null || warn "Could not fetch updates. Continuing with existing code."
        git reset --hard origin/main 2>/dev/null || warn "Could not update to latest. Continuing with existing code."
    else
        if [[ -d "$INSTALL_DIR" ]]; then
            warn "$INSTALL_DIR exists but is not a git repo. Backing up to ${INSTALL_DIR}.bak"
            mv "$INSTALL_DIR" "${INSTALL_DIR}.bak.$(date +%s)"
        fi

        mkdir -p "$(dirname "$INSTALL_DIR")"
        git clone "$REPO_URL" "$INSTALL_DIR" || {
            err "Failed to clone repository. Please check your internet connection."
            exit 1
        }
        info "Repository cloned successfully"
    fi

    cd "$INSTALL_DIR"

    # Ensure required directories exist
    mkdir -p user_tools user_rag db Logs
    info "Directory structure ready"
}

run_config_wizard() {
    step "Launching configuration wizard..."

    # Check if Python is available
    local PYTHON=""
    for py in python3 python; do
        if command -v "$py" &>/dev/null; then
            PYTHON="$py"
            break
        fi
    done

    if [[ -z "$PYTHON" ]]; then
        warn "Python 3 not found. Skipping interactive wizard — using defaults."
        write_default_env
        return
    fi

    # Install rich if not present
    if ! "$PYTHON" -c "import rich" 2>/dev/null; then
        detail "Installing 'rich' library for TUI..."
        "$PYTHON" -m pip install rich --quiet 2>/dev/null || {
            warn "Could not install rich. Using basic text input mode."
            basic_config
            return
        }
    fi

    # Write wizard to temp file so stdin stays connected to terminal
    _WIZARD_PY=$(mktemp /tmp/rigel_wizard.XXXXXX.py)
    cat > "$_WIZARD_PY" << 'PYEOF'
import os, sys, re
from pathlib import Path

sys.stdin = open("/dev/tty")
INSTALL_DIR = Path(sys.argv[1])
ENV_FILE = INSTALL_DIR / ".env"

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.text import Text
from rich import box

import io
console = Console(file=open("/dev/tty", "w"))

def banner():
    console.print(Panel.fit(
        "[bold cyan]RIGEL Engine[/] — Configuration Wizard\n"
        "Configure your inference backends, models, and server settings.",
        border_style="cyan"
    ))

def select_inference_engine():
    """Ask user to select primary inference engine."""
    console.print("\n[bold]Select your primary LLM backend:[/]")
    console.print(f"  [cyan]1[/] — [bold]groq[/]:    Groq Cloud (fast, cloud-hosted, requires API key)")
    console.print(f"  [cyan]2[/] — [bold]ollama[/]:  Ollama (local inference, privacy-first)")
    console.print(f"  [dim]3[/] — [dim][bold]deepseek[/]: DeepSeek (cloud API, strong coding models) — [yellow]coming soon[/][/]")

    choice = Prompt.ask("Choice", choices=["1", "2"], default="1")
    engine_map = {"1": "groq", "2": "ollama"}
    return engine_map[choice]

def ask_api_keys(engine):
    """Ask for API keys based on selected engine."""
    keys = {}
    if engine == "groq":
        val = Prompt.ask("Enter your Groq API key", default="")
        if val:
            keys["GROQ_API_KEY"] = val
    elif engine == "deepseek":
        val = Prompt.ask("Enter your DeepSeek API key", default="")
        if val:
            keys["DEEPSEEK_API_KEY"] = val

    # Optionally ask for OpenAI key as a fallback
    if Confirm.ask("Add an OpenAI API key as fallback?", default=False):
        val = Prompt.ask("Enter your OpenAI API key", default="")
        if val:
            keys["OPENAI_API_KEY"] = val

    return keys

def ask_ollama_config(engine):
    """Configure Ollama host if using ollama."""
    host = "http://localhost:11434"
    if engine == "ollama":
        host = Prompt.ask("Ollama host URL", default="http://localhost:11434")
    return host

def ask_models(engine):
    """Ask which models to use."""
    console.print("\n[bold]Model selection:[/]")
    defaults = {
        "groq":    "openai/gpt-oss-120b",
        "ollama":  "llama3.2",
        "deepseek":"deepseek-chat",
    }
    general = Prompt.ask("Main model", default=defaults.get(engine, defaults["groq"]))
    return general

def ask_tool_call_config(engine):
    """Configure tool-calling engine."""
    console.print("\n[bold]Tool-calling configuration:[/]")
    console.print("  The tool-call engine can differ from your main engine for speed/cost.")
    if Confirm.ask("Use a separate engine for tool calls?", default=False):
        tc_engine = Prompt.ask(
            "Tool-call engine",
            choices=["groq", "ollama"],
            default="groq"
        )
        tc_model = Prompt.ask("Tool-call model", default="qwen/qwen3-32b")
        return tc_engine, tc_model
    return "", ""

def ask_server_type():
    """Ask which server mode to use."""
    console.print("\n[bold]Server mode:[/]")
    modes = {
        "1": ("hybrid", "Web API (port 8000) + D-Bus service (recommended)"),
        "2": ("dbus",   "D-Bus service only (system integration)"),
        "3": ("web",    "Web API only (HTTP/WebSocket on port 8000)"),
    }
    for key, (name, desc) in modes.items():
        console.print(f"  [cyan]{key}[/] — [bold]{name}[/]: {desc}")

    choice = Prompt.ask("Choice", choices=["1", "2", "3"], default="1")
    mode_map = {"1": "hybrid", "2": "dbus", "3": "web"}
    return mode_map[choice]

def ask_voice():
    """Configure voice synthesis/recognition."""
    console.print("\n[bold]Voice configuration:[/]")
    if not Confirm.ask("Enable voice features? (Piper TTS + Whisper STT)", default=True):
        return "none", "none"

    voices = {
        "1": ("hal",  "English male voice"),
        "2": ("amy",  "English female voice"),
        "3": ("adam", "English male voice"),
    }
    for key, (name, desc) in voices.items():
        console.print(f"  [cyan]{key}[/] — [bold]{name}[/]: {desc}")
    voice_choice = Prompt.ask("TTS voice", choices=["1", "2", "3"], default="1")
    voice_map = {"1": "hal", "2": "amy", "3": "adam"}

    stt_models = {
        "1": ("tiny",  "Fast, smallest (~75MB)"),
        "2": ("base",  "Balanced (~145MB)"),
        "3": ("small", "Accurate (~488MB)"),
    }
    for key, (name, desc) in stt_models.items():
        console.print(f"  [cyan]{key}[/] — [bold]{name}[/]: {desc}")
    stt_choice = Prompt.ask("Whisper model size", choices=["1", "2", "3"], default="1")
    stt_map = {"1": "tiny", "2": "base", "3": "small"}

    return voice_map[voice_choice], stt_map[stt_choice]

def ask_rigel_claude():
    """Configure RigelClaude (Claude Code wrapper)."""
    if not Confirm.ask("Enable RigelClaude (Claude Code wrapper)?", default=False):
        return False, "", "", ""

    base_url = Prompt.ask("Anthropic API base URL", default="https://api.anthropic.com")
    auth_token = Prompt.ask("Anthropic auth token", default="")
    model = Prompt.ask("Default model", default="claude-sonnet-4-6")

    return True, base_url, auth_token, model

def ask_temperature():
    """Ask for temperature settings."""
    temp = Prompt.ask("Main temperature", default="0.3")
    tool_temp = Prompt.ask("Tool-call temperature", default="0.0")
    return temp, tool_temp

def write_env(config):
    """Write the .env file."""
    c = config
    lines = []

    lines.append("# RIGEL Engine — generated configuration")
    lines.append(f"INFERENCE_ENGINE={c['engine']}")
    lines.append("")

    if c.get("general_model"):
        lines.append(f"GENERAL_LLM_MODEL={c['general_model']}")

    # Engine-specific models
    if c['engine'] == 'groq':
        lines.append(f"GROQ_MODEL={c['general_model']}")
    elif c['engine'] == 'ollama':
        lines.append(f"OLLAMA_MODEL={c['general_model']}")
    elif c['engine'] == 'deepseek':
        lines.append(f"DEEPSEEK_MODEL={c['general_model']}")

    # Ollama host
    lines.append(f"OLLAMA_HOST={c.get('ollama_host', 'http://localhost:11434')}")
    lines.append("")

    # API keys
    for key_name, key_val in c.get("api_keys", {}).items():
        if key_val:
            lines.append(f"{key_name}={key_val}")

    if c['engine'] == 'deepseek' and 'DEEPSEEK_API_KEY' not in c.get('api_keys', {}):
        lines.append("DEEPSEEK_API_KEY=")

    lines.append("")
    lines.append("# Tool calling")
    if c.get('tool_call_engine'):
        lines.append(f"TOOL_CALL_ENGINE={c['tool_call_engine']}")
        lines.append(f"TOOL_CALL_MODEL={c['tool_call_model']}")
    lines.append("")

    lines.append("# Temperature")
    lines.append(f"TEMPERATURE={c.get('temperature', '0.3')}")
    lines.append(f"TOOL_TEMPERATURE={c.get('tool_temperature', '0.0')}")
    lines.append("")

    lines.append("# Server")
    lines.append(f"SERVER_TYPE={c.get('server_type', 'hybrid')}")
    lines.append("")

    lines.append("# Voice")
    lines.append(f"VOICE={c.get('voice', 'hal')}")
    lines.append(f"VOICE_RECOGNITION_MODEL={c.get('voice_model', 'tiny')}")
    lines.append("")

    # D-Bus
    lines.append("# D-Bus system socket")
    lines.append("DBUS_SYSTEM_BUS_ADDRESS=unix:path=/run/dbus/system_bus_socket")
    lines.append("")

    # MCP
    lines.append("# MCP tools server")
    lines.append("RIGEL_MCP_TOOLS_SSE_URL=http://localhost:8001/sse")
    lines.append("")

    # System prompt
    lines.append("# System prompt")
    lines.append('RIGEL_SYSTEM_PROMPT="You are RIGEL, a helpful assistant developed by Zerone Laboratories."')
    lines.append("")

    # RigelClaude
    if c.get('rigel_claude_enabled'):
        lines.append("# RigelClaude extension")
        lines.append("RIGEL_CLAUDE_ENABLED=true")
        lines.append(f"ANTHROPIC_BASE_URL={c.get('claude_base_url', '')}")
        lines.append(f"ANTHROPIC_AUTH_TOKEN={c.get('claude_auth_token', '')}")
        lines.append(f"ANTHROPIC_MODEL={c.get('claude_model', '')}")
        lines.append(f"ANTHROPIC_DEFAULT_OPUS_MODEL={c.get('claude_model', '')}")
        lines.append(f"ANTHROPIC_DEFAULT_SONNET_MODEL={c.get('claude_model', '')}")
        lines.append(f"ANTHROPIC_DEFAULT_HAIKU_MODEL=claude-haiku-4-5-20251001")
        lines.append("")

    lines.append("# Misc")
    lines.append("SUMMARIZE_CONVERSATIONS=true")
    lines.append("VECTOR_CACHE_ENABLED=true")
    lines.append("CLEAR_VECTOR_CACHE_ON_STARTUP=false")
    lines.append("PRODUCTION=true")
    lines.append("PYTHONUNBUFFERED=1")

    env_content = "\n".join(lines) + "\n"
    ENV_FILE.write_text(env_content)

def show_summary(config):
    """Show a summary of the configuration before writing."""
    table = Table(title="Configuration Summary", box=box.ROUNDED)
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Inference Engine", config['engine'])
    table.add_row("Main Model", config.get('general_model', 'default'))
    table.add_row("Server Mode", config.get('server_type', 'hybrid'))

    api_keys = config.get('api_keys', {})
    for k, v in api_keys.items():
        masked = v[:8] + "..." + v[-4:] if len(v) > 12 else v[:4] + "****"
        table.add_row(k, masked)

    if config.get('tool_call_engine'):
        table.add_row("Tool-Call Engine", config['tool_call_engine'])
        table.add_row("Tool-Call Model", config['tool_call_model'])

    table.add_row("Temperature", config.get('temperature', '0.3'))
    table.add_row("Voice", config.get('voice', 'none'))
    table.add_row("Whisper Model", config.get('voice_model', 'none'))

    if config.get('rigel_claude_enabled'):
        table.add_row("RigelClaude", "Enabled ✓")

    console.print(table)

def main():
    banner()

    config = {}

    # 1. Inference engine
    config['engine'] = select_inference_engine()

    # 2. API keys
    config['api_keys'] = ask_api_keys(config['engine'])

    # 3. Ollama host
    config['ollama_host'] = ask_ollama_config(config['engine'])

    # 4. Models
    config['general_model'] = ask_models(config['engine'])

    # 5. Tool-call config
    tc_engine, tc_model = ask_tool_call_config(config['engine'])
    config['tool_call_engine'] = tc_engine
    config['tool_call_model'] = tc_model

    # 6. Server type
    config['server_type'] = ask_server_type()

    # 7. Voice
    voice, voice_model = ask_voice()
    config['voice'] = voice
    config['voice_model'] = voice_model

    # 8. Temperature
    temp, tool_temp = ask_temperature()
    config['temperature'] = temp
    config['tool_temperature'] = tool_temp

    # 9. RigelClaude
    claude_enabled, claude_url, claude_token, claude_model = ask_rigel_claude()
    config['rigel_claude_enabled'] = claude_enabled
    config['claude_base_url'] = claude_url
    config['claude_auth_token'] = claude_token
    config['claude_model'] = claude_model

    # Show summary and confirm
    console.print("\n")
    show_summary(config)

    if Confirm.ask("\nWrite this configuration?", default=True):
        write_env(config)
        console.print("\n[green]✓ Configuration written to .env[/]")
    else:
        console.print("[yellow]Configuration cancelled. Using defaults.[/]")
        write_env({
            'engine': 'groq',
            'general_model': 'openai/gpt-oss-120b',
            'ollama_host': 'http://localhost:11434',
            'api_keys': {},
            'tool_call_engine': 'groq',
            'tool_call_model': 'qwen/qwen3-32b',
            'server_type': 'hybrid',
            'voice': 'hal',
            'voice_model': 'tiny',
            'temperature': '0.3',
            'tool_temperature': '0.0',
            'rigel_claude_enabled': False,
        })
        console.print("[yellow]Default configuration written.[/]")

if __name__ == "__main__":
    main()
PYEOF

    "$PYTHON" "$_WIZARD_PY" "$INSTALL_DIR" </dev/tty
    cp "$_WIZARD_PY" "$INSTALL_DIR/rigel-config-wizard.py"
    chmod 644 "$INSTALL_DIR/rigel-config-wizard.py"
    rm -f "$_WIZARD_PY"

    info "Configuration wizard completed"
}

# Fallback: basic text-based config if rich/Python not available
basic_config() {
    step "Basic configuration (text mode)..."
    local ENV_FILE="$INSTALL_DIR/.env"

    echo "Select inference engine:"
    echo "  1) groq (cloud)"
    echo "  2) ollama (local)"
    echo "  3) deepseek (cloud) — coming soon, unavailable"
    read -rp "Choice [1-2]: " engine_choice </dev/tty
    case "$engine_choice" in
        1) ENGINE="groq" ;;
        2) ENGINE="ollama" ;;
        *) ENGINE="groq" ;;
    esac

    read -rp "Enter model name (default: depends on engine): " MODEL </dev/tty
    [[ -z "$MODEL" ]] && case "$ENGINE" in
        groq) MODEL="openai/gpt-oss-120b" ;;
        ollama) MODEL="llama3.2" ;;
        deepseek) MODEL="deepseek-chat" ;;
    esac

    cat > "$ENV_FILE" << EOF
# RIGEL Engine configuration
INFERENCE_ENGINE=$ENGINE
GENERAL_LLM_MODEL=$MODEL
SERVER_TYPE=hybrid
VOICE=hal
VOICE_RECOGNITION_MODEL=tiny
TEMPERATURE=0.3
TOOL_TEMPERATURE=0.0
RIGEL_MCP_TOOLS_SSE_URL=http://localhost:8001/sse
DBUS_SYSTEM_BUS_ADDRESS=unix:path=/run/dbus/system_bus_socket
SUMMARIZE_CONVERSATIONS=true
PRODUCTION=true
PYTHONUNBUFFERED=1
EOF
    info "Basic configuration written"
}

# Write a minimal default .env if nothing else works
write_default_env() {
    cat > "$INSTALL_DIR/.env" << 'EOF'
INFERENCE_ENGINE=groq
GENERAL_LLM_MODEL=openai/gpt-oss-120b
SERVER_TYPE=hybrid
VOICE=hal
VOICE_RECOGNITION_MODEL=tiny
TEMPERATURE=0.3
TOOL_TEMPERATURE=0.0
RIGEL_MCP_TOOLS_SSE_URL=http://localhost:8001/sse
DBUS_SYSTEM_BUS_ADDRESS=unix:path=/run/dbus/system_bus_socket
SUMMARIZE_CONVERSATIONS=true
PRODUCTION=true
PYTHONUNBUFFERED=1
EOF
}

fix_docker_compose_volumes() {
    step "Adjusting Docker volume mounts for current user..."

    local USER_HOME
    USER_HOME=$(getent passwd "$SUDO_USER" 2>/dev/null | cut -d: -f6 || echo "/home/$SUDO_USER")
    local USER_UID
    USER_UID=$(id -u "$SUDO_USER" 2>/dev/null || echo 1000)

    # Update docker-compose.yml to replace hardcoded /home/zerone paths
    if [[ -f "$INSTALL_DIR/docker-compose.yml" ]]; then
        sed -i "s|/home/zerone|$USER_HOME|g" "$INSTALL_DIR/docker-compose.yml"
        info "Volume paths updated for user: $SUDO_USER (home: $USER_HOME)"
    fi

    # Also set HOST_UID and HOST_HOME in .env
    if [[ -f "$INSTALL_DIR/.env" ]]; then
        cat >> "$INSTALL_DIR/.env" << EOF
HOST_UID=$USER_UID
HOST_HOME=$USER_HOME
EOF
    fi
}

build_docker() {
    step "Building RIGEL Docker image..."
    cd "$INSTALL_DIR"
    docker compose build --build-arg SKIP_PYTHON_DEPS=false 2>&1 | tail -20
    info "Docker image built successfully"
}

start_docker() {
    step "Starting RIGEL server..."
    cd "$INSTALL_DIR"
    docker compose up -d rigel-server
    info "Docker container started"

    # Wait briefly and check status
    sleep 3
    if docker compose ps 2>/dev/null | grep -q "Up"; then
        info "RIGEL server is running"
    else
        warn "Container may still be starting. Check logs with: docker compose logs -f"
    fi
}

show_post_install() {
    echo ""
    echo -e "${BOLD}${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}${CYAN}║         RIGEL Engine — Installation Complete               ║${NC}"
    echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    echo -e "${BOLD}📍 Useful Commands:${NC}"
    echo ""

    echo -e "  ${CYAN}View logs:${NC}"
    echo "    docker compose -f $INSTALL_DIR/docker-compose.yml logs -f"
    echo ""

    echo -e "  ${CYAN}Restart server:${NC}"
    echo "    docker compose -f $INSTALL_DIR/docker-compose.yml restart"
    echo ""

    echo -e "  ${CYAN}Stop server:${NC}"
    echo "    docker compose -f $INSTALL_DIR/docker-compose.yml down"
    echo ""

    echo -e "  ${CYAN}D-Bus test (if hybrid/dbus mode):${NC}"
    echo "    dbus-send --system --dest=com.rigel.RigelService --print-reply \\"
    echo "      /com/rigel/RigelService com.rigel.RigelService.Ping"
    echo ""

    echo -e "${BOLD}🔧 MCP Tools Server (Host-side):${NC}"
    echo ""
    echo "  The MCP tools server runs on the host (port 8001) for system access."
    echo "  Start it manually:"
    echo ""
    echo -e "    ${CYAN}cd $INSTALL_DIR && python core/mcp/rigel_tools_server.py${NC}"
    echo ""
    echo "  Or use the convenience script:"
    echo -e "    ${CYAN}$INSTALL_DIR/scripts/host-up.sh${NC}"
    echo ""

    echo -e "${BOLD}🔄 Auto-start via systemd:${NC}"
    echo ""
    echo "  Create a systemd service to auto-start RIGEL on boot:"
    echo ""
    local USER_HOME
    USER_HOME=$(getent passwd "$SUDO_USER" 2>/dev/null | cut -d: -f6 || echo "/home/$SUDO_USER")
    cat << SERVICE
  sudo tee /etc/systemd/system/rigel-engine.service << 'UNIT'
[Unit]
Description=RIGEL Engine (Docker + MCP Tools)
After=network.target docker.service
Wants=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/scripts/host-up.sh
ExecStop=docker compose -f $INSTALL_DIR/docker-compose.yml down
Restart=on-failure
RestartSec=5
User=root

[Install]
WantedBy=multi-user.target
UNIT
SERVICE
    echo ""
    echo "  Then enable it:"
    echo -e "    ${CYAN}sudo systemctl daemon-reload${NC}"
    echo -e "    ${CYAN}sudo systemctl enable --now rigel-engine.service${NC}"
    echo ""

    echo -e "${BOLD}🌐 Web Interface:${NC}"
    echo "  If running in hybrid or web mode: http://localhost:8000"
    echo ""

    echo -e "${BOLD}📁 Installation directory:${NC} $INSTALL_DIR"
    echo -e "${BOLD}📁 Configuration file:${NC}    $INSTALL_DIR/.env"
    echo ""
}

install_shell_integration() {
    step "Setting up RIGEL shell integration..."

    # Get the real user (who ran sudo)
    local real_user="${SUDO_USER:-$USER}"
    local user_home

    if [[ "$real_user" == "root" ]]; then
        user_home="/root"
    else
        user_home=$(getent passwd "$real_user" 2>/dev/null | cut -d: -f6 || echo "/home/$real_user")
    fi

    # Detect shell and RC file
    local shell_rc=""
    local shell_name=""
    local user_shell
    user_shell=$(getent passwd "$real_user" 2>/dev/null | cut -d: -f7)

    if [[ "$user_shell" == *"zsh"* ]]; then
        shell_rc="$user_home/.zshrc"
        shell_name="zsh"
    elif [[ "$user_shell" == *"bash"* ]]; then
        shell_rc="$user_home/.bashrc"
        shell_name="bash"
    elif [[ -f "$user_home/.zshrc" ]]; then
        shell_rc="$user_home/.zshrc"
        shell_name="zsh"
    elif [[ -f "$user_home/.bashrc" ]]; then
        shell_rc="$user_home/.bashrc"
        shell_name="bash"
    fi

    if [[ -z "$shell_rc" ]]; then
        detail "No .zshrc or .bashrc found for user $real_user. Skipping shell integration."
        return
    fi

    # Check if already installed
    if grep -q "rigel-shell-integration\|rigel_execute_query\|rigel_query\|rigel_help" "$shell_rc" 2>/dev/null; then
        info "RIGEL shell commands already present in $shell_rc"
        return
    fi

    echo ""
    echo -e "  ${BOLD}${CYAN}┌─────────────────────────────────────────────┐${NC}"
    echo -e "  ${BOLD}${CYAN}│  Add experimental RIGEL shell commands to    │${NC}"
    echo -e "  ${BOLD}${CYAN}│  your environment?                            │${NC}"
    echo -e "  ${BOLD}${CYAN}│  (${YELLOW}$shell_rc${CYAN})${NC}"
    echo -e "  ${BOLD}${CYAN}└─────────────────────────────────────────────┘${NC}"
    echo ""

    read -rp "  Add experimental rigel shell commands to environment? [y/N]: " answer </dev/tty
    case "$answer" in
        [Yy]|[Yy][Ee][Ss]) ;;
        *)
            detail "Shell integration skipped. You can manually source it later:"
            detail "  source $INSTALL_DIR/rigel-shell-integration.sh"
            return ;;
    esac

    # Write shell integration file to install directory
    local integration_file="$INSTALL_DIR/rigel-shell-integration.sh"
    detail "Writing shell integration to $integration_file ..."

    # Write install directory reference (expanded) first, then append the quoted heredoc
    echo "_RIGEL_INSTALL_DIR=\"$INSTALL_DIR\"" > "$integration_file"
    cat >> "$integration_file" << 'RIGELSHELL'
# RIGEL Engine — Shell Integration
# Generated by RIGEL installer.
# Source this from your .zshrc or .bashrc

# ── Color helpers (zsh + bash) ───────────────────────────────────────────────
if [[ -n "$ZSH_VERSION" ]]; then
    _rigel_color_red="%F{red}"
    _rigel_color_green="%F{green}"
    _rigel_color_yellow="%F{yellow}"
    _rigel_color_blue="%F{blue}"
    _rigel_color_cyan="%F{cyan}"
    _rigel_color_magenta="%F{magenta}"
    _rigel_color_white="%F{white}"
    _rigel_color_dim="%F{8}"
    _rigel_color_reset="%f"
    _rigel_color_bold="%B"
    _rigel_color_bold_off="%b"
else
    _rigel_color_red='\033[0;31m'
    _rigel_color_green='\033[0;32m'
    _rigel_color_yellow='\033[1;33m'
    _rigel_color_blue='\033[0;34m'
    _rigel_color_cyan='\033[0;36m'
    _rigel_color_magenta='\033[0;35m'
    _rigel_color_white='\033[0;37m'
    _rigel_color_dim='\033[2m'
    _rigel_color_reset='\033[0m'
    _rigel_color_bold='\033[1m'
    _rigel_color_bold_off='\033[22m'
fi

# ── Logging ──────────────────────────────────────────────────────────────────
rigel_log() {
    local level="$1"
    local message="$2"
    local timestamp
    timestamp=$(date '+%H:%M:%S')

    if [[ -n "$ZSH_VERSION" ]]; then
        case "$level" in
            "info"|"INFO")
                print -P "${_rigel_color_blue}[INFO]${_rigel_color_reset} ${_rigel_color_dim}[$timestamp]${_rigel_color_reset} $message" ;;
            "warn"|"WARN"|"warning"|"WARNING")
                print -P "${_rigel_color_yellow}[WARN]${_rigel_color_reset} ${_rigel_color_dim}[$timestamp]${_rigel_color_reset} $message" ;;
            "error"|"ERROR")
                print -P "${_rigel_color_red}[ERROR]${_rigel_color_reset} ${_rigel_color_dim}[$timestamp]${_rigel_color_reset} $message" ;;
            "success"|"SUCCESS")
                print -P "${_rigel_color_green}[SUCCESS]${_rigel_color_reset} ${_rigel_color_dim}[$timestamp]${_rigel_color_reset} $message" ;;
            *)
                print -P "${_rigel_color_white}[LOG]${_rigel_color_reset} ${_rigel_color_dim}[$timestamp]${_rigel_color_reset} $message" ;;
        esac
    else
        case "$level" in
            "info"|"INFO")
                echo -e "${_rigel_color_blue}[INFO]${_rigel_color_reset} ${_rigel_color_dim}[$timestamp]${_rigel_color_reset} $message" ;;
            "warn"|"WARN"|"warning"|"WARNING")
                echo -e "${_rigel_color_yellow}[WARN]${_rigel_color_reset} ${_rigel_color_dim}[$timestamp]${_rigel_color_reset} $message" ;;
            "error"|"ERROR")
                echo -e "${_rigel_color_red}[ERROR]${_rigel_color_reset} ${_rigel_color_dim}[$timestamp]${_rigel_color_reset} $message" ;;
            "success"|"SUCCESS")
                echo -e "${_rigel_color_green}[SUCCESS]${_rigel_color_reset} ${_rigel_color_dim}[$timestamp]${_rigel_color_reset} $message" ;;
            *)
                echo -e "${_rigel_color_white}[LOG]${_rigel_color_reset} ${_rigel_color_dim}[$timestamp]${_rigel_color_reset} $message" ;;
        esac
    fi
}

alias rigel_info='rigel_log info'
alias rigel_warn='rigel_log warn'
alias rigel_error='rigel_log error'
alias rigel_success='rigel_log success'

# ── Spinner animation ────────────────────────────────────────────────────────
rigel_spinner() {
    local pid=$1
    local delay=0.1
    local spinstr='|/-\'
    local message="${2:-Processing}"

    while kill -0 "$pid" 2>/dev/null; do
        local temp=${spinstr#?}
        printf "\r\033[36m[%c]\033[0m \033[90m%s...\033[0m" "$spinstr" "$message"
        local spinstr=$temp${spinstr%"$temp"}
        sleep $delay
    done
    printf "\r\033[K\n"
}

# ── D-Bus query executor ─────────────────────────────────────────────────────
rigel_execute_query() {
    local method="$1"
    shift
    local message=""
    local args=()
    local no_animate=false

    while [ $# -gt 0 ]; do
        case "$1" in
            --no_animate)
                no_animate=true
                shift ;;
            *"Processing"*|*"Querying"*|*"Synthesizing"*|*"Transcribing"*|*"Retrieving"*|*"Analyzing"*|*"Cloning"*|*"Launching"*|*"Reviewing"*|*"Debugging"*|*"Refactoring"*|*"Explaining"*|*"Executing"*|*"Starting"*|*"Stopping"*|*"Checking"*|*"Generating"*)
                message="$1"
                shift
                break ;;
            *)
                args+=("$1")
                shift ;;
        esac
    done

    if [ -z "$message" ]; then
        message="Querying RIGEL"
    fi

    local temp_file
    temp_file=$(mktemp)
    local raw_file
    raw_file=$(mktemp)
    local error_file
    error_file=$(mktemp)
    local timeout_duration=120

    set +m

    {
        timeout $timeout_duration dbus-send --system \
            --dest=com.rigel.RigelService \
            --type=method_call \
            --print-reply \
            --reply-timeout=120000 \
            /com/rigel/RigelService \
            "com.rigel.RigelService.$method" \
            "${args[@]}" 2>"$error_file" > "$raw_file"
        echo $? > "${temp_file}.exit"
    } &

    local query_pid=$!
    local spinner_pid=""

    if [ "$no_animate" = false ]; then
        { rigel_spinner $query_pid "$message"; } &
        spinner_pid=$!
    fi

    wait $query_pid 2>/dev/null

    if [ -n "$spinner_pid" ]; then
        kill $spinner_pid 2>/dev/null
        wait $spinner_pid 2>/dev/null
    fi

    set -m

    local exit_code=1
    if [ -f "${temp_file}.exit" ]; then
        exit_code=$(cat "${temp_file}.exit")
        rm -f "${temp_file}.exit"
    fi

    local response=""
    if [ $exit_code -eq 0 ] && [ -f "$raw_file" ]; then
        response=$(awk '
        BEGIN { in_string = 0; response = "" }
        /string "/ {
            in_string = 1
            start = index($0, "string \"") + 8
            content = substr($0, start)
            if (content ~ /"$/) {
                gsub(/"$/, "", content)
                response = content
                in_string = 0
            } else {
                response = content "\n"
            }
            next
        }
        in_string == 1 {
            if ($0 ~ /"$/) {
                gsub(/"$/, "", $0)
                response = response $0
                in_string = 0
            } else {
                response = response $0 "\n"
            }
        }
        END {
            gsub(/\n$/, "", response)
            print response
        }
        ' "$raw_file")
    fi

    local error_output
    error_output=$(cat "$error_file" 2>/dev/null)

    rm -f "$temp_file" "$raw_file" "$error_file"

    if [ $exit_code -eq 124 ]; then
        rigel_error "Query timed out after 120 seconds"
        return 1
    elif [ $exit_code -ne 0 ]; then
        if [ -n "$error_output" ]; then
            rigel_error "D-Bus call failed: $error_output"
        else
            rigel_error "D-Bus call failed with exit code $exit_code"
        fi
        return 1
    elif [ -z "$response" ]; then
        rigel_error "No response received from RIGEL service"
        if [ -n "$error_output" ]; then
            rigel_warn "Error output: $error_output"
        fi
        return 1
    else
        response=$(printf '%s' "$response" | sed -E 's/^\s*\[\-\]\s*Querying RIGEL\.*\s*//')
        printf "%s\n" "$response"
        return 0
    fi
}

# ── Service check helper ─────────────────────────────────────────────────────
_rigel_service_running() {
    dbus-send --system --dest=org.freedesktop.DBus --type=method_call --print-reply \
        /org/freedesktop/DBus org.freedesktop.DBus.NameHasOwner \
        string:com.rigel.RigelService 2>/dev/null | grep -q "boolean true"
}

# ── Query ────────────────────────────────────────────────────────────────────
rigel_query() {
    local no_animate=false
    local query_args=()

    while [ $# -gt 0 ]; do
        case "$1" in
            --no_animate)
                no_animate=true
                shift ;;
            *)
                query_args+=("$1")
                shift ;;
        esac
    done

    if [ ${#query_args[@]} -eq 0 ]; then
        rigel_error "Usage: rigel_query [--no_animate] 'your question here'"
        return 1
    fi

    local query="${query_args[*]}"

    if [ "$no_animate" = false ]; then
        rigel_info "Querying RIGEL: $query"
    fi

    if ! _rigel_service_running; then
        rigel_error "RIGEL D-Bus service is not running. Please start the service first."
        return 1
    fi

    if [ "$no_animate" = true ]; then
        rigel_execute_query "Query" --no_animate "string:\"$query\"" "Processing query"
    else
        rigel_execute_query "Query" "string:\"$query\"" "Processing query"
    fi
}

# ── Query with memory ────────────────────────────────────────────────────────
rigel_memory() {
    if [ $# -lt 2 ]; then
        rigel_error "Usage: rigel_memory 'conversation_id' 'your question here'"
        rigel_info "Example: rigel_memory 'chat_001' 'Remember that I like Python programming'"
        return 1
    fi

    local id="$1"
    shift
    local query="$*"
    rigel_info "Querying RIGEL with memory (ID: $id): $query"

    if ! _rigel_service_running; then
        rigel_error "RIGEL D-Bus service is not running. Please start the service first."
        return 1
    fi

    rigel_execute_query "QueryWithMemory" "string:\"$query\"" "string:\"$id\"" "Processing memory query"
}

# ── Think (reasoning) ────────────────────────────────────────────────────────
rigel_think() {
    if [ $# -eq 0 ]; then
        rigel_error "Usage: rigel_think 'your question here'"
        rigel_info "Uses the model's reasoning capability before answering."
        return 1
    fi

    local query="$*"
    rigel_info "Thinking about: $query"

    if ! _rigel_service_running; then
        rigel_error "RIGEL D-Bus service is not running. Please start the service first."
        return 1
    fi

    rigel_execute_query "QueryThink" "string:\"$query\"" "Processing reasoning"
}

# ── Natural Language ─────────────────────────────────────────────────────────
rigel_natural_language() {
    if [ $# -eq 0 ]; then
        rigel_error "Usage: rigel_natural_language [conversation_id] 'your request here'"
        rigel_info "Examples:"
        rigel_info "  rigel_natural_language 'check disk usage and explain it simply'"
        rigel_info "  rigel_natural_language 'chat_001' 'set volume to 50 and confirm'"
        return 1
    fi

    local id=""
    local query=""

    if [ $# -eq 1 ]; then
        id="nl_$(date +%s)"
        query="$1"
    else
        id="$1"
        shift
        query="$*"
    fi

    if [ -z "$query" ]; then
        rigel_error "Empty query. Please provide a request."
        return 1
    fi

    if ! _rigel_service_running; then
        rigel_error "RIGEL D-Bus service is not running. Please start the service first."
        return 1
    fi

    rigel_execute_query "RigelNaturalLanguage" "string:\"$query\"" "string:\"$id\"" "Processing natural language request"
}
alias rigel_nl='rigel_natural_language'

# ── Tools ────────────────────────────────────────────────────────────────────
rigel_tools() {
    if [ $# -eq 0 ]; then
        rigel_error "Usage: rigel_tools 'your task here'"
        return 1
    fi

    local user_query="$*"
    local current_dir
    current_dir="$(pwd)"

    local enhanced_query
    enhanced_query="Working Directory: $current_dir | User request: $user_query"

    if ! _rigel_service_running; then
        rigel_error "RIGEL D-Bus service is not running."
        return 1
    fi

    rigel_info "Running toolcall..."

    local tool_output
    tool_output="$(
        rigel_execute_query \
            QueryWithTools \
            --no_animate \
            "string:\"$enhanced_query\""
    )"

    rigel_info "Summarizing tool output..."

    local safe_tool_output="$tool_output"
    if [ -z "$safe_tool_output" ]; then
        safe_tool_output="tool_returned_no_output"
    fi

    local max_chars=60000
    if [ ${#safe_tool_output} -gt $max_chars ]; then
        safe_tool_output="${safe_tool_output:0:$max_chars}\n[Note: Output truncated to ${max_chars} chars]"
    fi

    local escaped_output
    escaped_output="$(printf '%s' "$safe_tool_output" | sed -e 's/{/{{/g' -e 's/}/}}/g')"

    local summary_prompt="Summarize the following tool output for the user:\n${escaped_output}"

    rigel_execute_query \
        Query \
        --no_animate \
        "string:\"$summary_prompt\""
}

# ── Vision ───────────────────────────────────────────────────────────────────
rigel_vision() {
    if [ $# -lt 1 ]; then
        rigel_error "Usage: rigel_vision 'path/to/image.png' ['optional prompt']"
        rigel_info "Example: rigel_vision 'screenshot.png' 'Describe what you see'"
        return 1
    fi

    local image_path="$1"
    local prompt="${2:-Describe what you see in this image.}"

    if [ ! -f "$image_path" ]; then
        rigel_error "Image file not found: $image_path"
        return 1
    fi

    if ! _rigel_service_running; then
        rigel_error "RIGEL D-Bus service is not running. Please start the service first."
        return 1
    fi

    rigel_info "Analyzing image: $image_path"
    rigel_execute_query "AnalyzeImage" "string:\"$image_path\"" "string:\"$prompt\"" "Analyzing image"
}

# ── Speech Synthesis ─────────────────────────────────────────────────────────
rigel_speak() {
    if [ -z "$1" ]; then
        rigel_error "Usage: rigel_speak 'text to synthesize' [mode] [voice]"
        rigel_info "Modes: chunk (default), stream, file"
        return 1
    fi

    local text="$1"
    local mode="${2:-chunk}"
    local voice="${3:-}"

    if ! _rigel_service_running; then
        rigel_error "RIGEL D-Bus service is not running. Please start the service first."
        return 1
    fi

    rigel_info "Synthesizing text with mode: $mode"
    local response
    if [ -n "$voice" ]; then
        response=$(rigel_execute_query "SynthesizeText" "string:\"$text\"" "string:$mode" "string:$voice" "Synthesizing speech")
    else
        response=$(rigel_execute_query "SynthesizeText" "string:\"$text\"" "string:$mode" "string:" "Synthesizing speech")
    fi

    if [ $? -eq 0 ] && [ -n "$response" ]; then
        rigel_success "$response"
    else
        rigel_error "Failed to synthesize text"
        return 1
    fi
}

# ── Voice Management ─────────────────────────────────────────────────────────
rigel_voice_list() {
    rigel_info "Retrieving available voices..."

    if ! _rigel_service_running; then
        rigel_error "RIGEL D-Bus service is not running. Please start the service first."
        return 1
    fi

    rigel_execute_query "ListVoices" "Retrieving voice list"
}

rigel_voice_set() {
    if [ -z "$1" ]; then
        rigel_error "Usage: rigel_voice_set 'voice_name'"
        rigel_info "Use 'rigel_voice_list' to see available voices."
        return 1
    fi

    local voice="$1"

    if ! _rigel_service_running; then
        rigel_error "RIGEL D-Bus service is not running. Please start the service first."
        return 1
    fi

    rigel_info "Setting voice to: $voice"
    rigel_execute_query "SetVoice" "string:\"$voice\"" "Retrieving voice list"
}

rigel_voice_clone() {
    if [ $# -lt 2 ]; then
        rigel_error "Usage: rigel_voice_clone 'path/to/sample.mp3' 'voice_name' [language]"
        rigel_info "Example: rigel_voice_clone 'my_voice.mp3' 'my_clone'"
        return 1
    fi

    local mp3_path="$1"
    local voice_name="$2"
    local language="${3:-English (U.S.)}"

    if [ ! -f "$mp3_path" ]; then
        rigel_error "Audio file not found: $mp3_path"
        return 1
    fi

    if ! _rigel_service_running; then
        rigel_error "RIGEL D-Bus service is not running. Please start the service first."
        return 1
    fi

    rigel_info "Cloning voice from: $mp3_path"
    rigel_execute_query "CloneVoice" "string:\"$mp3_path\"" "string:\"$voice_name\"" "string:\"$language\"" "Cloning voice"
}

# ── Audio Transcription ──────────────────────────────────────────────────────
rigel_transcribe() {
    if [ -z "$1" ]; then
        rigel_error "Usage: rigel_transcribe '/path/to/audio/file' [model]"
        rigel_info "Models: tiny (default), base, small, medium, large"
        return 1
    fi

    local audio_file="$1"
    local model="${2:-small}"

    if [ ! -f "$audio_file" ]; then
        rigel_error "Audio file not found: $audio_file"
        return 1
    fi

    rigel_info "Transcribing audio file: $audio_file (model: $model)"

    if ! _rigel_service_running; then
        rigel_error "RIGEL D-Bus service is not running. Please start the service first."
        return 1
    fi

    rigel_execute_query "RecognizeAudio" "string:\"$audio_file\"" "string:\"$model\"" "Transcribing audio"
}

# ── Live Voice Recognition ───────────────────────────────────────────────────
rigel_live_transcribe() {
    if [ $# -lt 1 ]; then
        rigel_error "Usage: rigel_live_transcribe start|stop|status [config_json]"
        rigel_info "Examples:"
        rigel_info "  rigel_live_transcribe start"
        rigel_info "  rigel_live_transcribe start '{\"model\":\"tiny.en\",\"capture_device\":-1}'"
        rigel_info "  rigel_live_transcribe stop"
        rigel_info "  rigel_live_transcribe status"
        return 1
    fi

    local action="$1"
    local config_json="${2:-{}}"

    if ! _rigel_service_running; then
        rigel_error "RIGEL D-Bus service is not running. Please start the service first."
        return 1
    fi

    case "$action" in
        start)
            rigel_info "Starting live voice recognition..."
            rigel_execute_query "LiveVoiceRecognition" "string:start" "string:$config_json" "Starting live recognition"
            ;;
        stop)
            rigel_info "Stopping live voice recognition..."
            rigel_execute_query "LiveVoiceRecognition" "string:stop" "string:$config_json" "Stopping live recognition"
            ;;
        status)
            rigel_execute_query "LiveVoiceRecognition" "string:status" "string:$config_json" "Checking recognition status"
            ;;
        *)
            rigel_error "Unknown action: $action. Use start, stop, or status."
            return 1
            ;;
    esac
}

# ── Coding Agent ─────────────────────────────────────────────────────────────
rigel_coding_generate() {
    if [ $# -lt 1 ]; then
        rigel_error "Usage: rigel_coding_generate 'specification' [language]"
        rigel_info "Example: rigel_coding_generate 'Create a REST API for a todo app' python"
        return 1
    fi

    local spec="$1"
    local lang="${2:-python}"

    if ! _rigel_service_running; then
        rigel_error "RIGEL D-Bus service is not running. Please start the service first."
        return 1
    fi

    rigel_info "Generating code ($lang): $spec"
    rigel_execute_query "CodingAgentGenerateCode" "string:\"$spec\"" "string:\"$lang\"" "Generating code"
}

rigel_coding_review() {
    if [ $# -lt 1 ]; then
        rigel_error "Usage: rigel_coding_review 'path/to/code.py' [language]"
        rigel_info "Example: rigel_coding_review '~/project/main.py' python"
        return 1
    fi

    local file_path="$1"
    local lang="${2:-python}"

    if [ ! -f "$file_path" ]; then
        rigel_error "File not found: $file_path"
        return 1
    fi

    local code
    code=$(cat "$file_path")

    if ! _rigel_service_running; then
        rigel_error "RIGEL D-Bus service is not running. Please start the service first."
        return 1
    fi

    rigel_info "Reviewing code: $file_path"
    rigel_execute_query "CodingAgentReviewCode" "string:\"$code\"" "string:\"$lang\"" "Reviewing code"
}

rigel_coding_debug() {
    if [ $# -lt 2 ]; then
        rigel_error "Usage: rigel_coding_debug 'path/to/code.py' 'error message' [language]"
        rigel_info "Example: rigel_coding_debug 'main.py' 'TypeError at line 42' python"
        return 1
    fi

    local file_path="$1"
    local error_msg="$2"
    local lang="${3:-python}"

    if [ ! -f "$file_path" ]; then
        rigel_error "File not found: $file_path"
        return 1
    fi

    local code
    code=$(cat "$file_path")

    if ! _rigel_service_running; then
        rigel_error "RIGEL D-Bus service is not running. Please start the service first."
        return 1
    fi

    rigel_info "Debugging code: $file_path"
    rigel_execute_query "CodingAgentDebugCode" "string:\"$code\"" "string:\"$error_msg\"" "string:\"$lang\"" "Debugging code"
}

rigel_coding_refactor() {
    if [ $# -lt 2 ]; then
        rigel_error "Usage: rigel_coding_refactor 'path/to/code.py' 'refactoring instructions' [language]"
        rigel_info "Example: rigel_coding_refactor 'main.py' 'Extract database logic into separate module' python"
        return 1
    fi

    local file_path="$1"
    local instructions="$2"
    local lang="${3:-python}"

    if [ ! -f "$file_path" ]; then
        rigel_error "File not found: $file_path"
        return 1
    fi

    local code
    code=$(cat "$file_path")

    if ! _rigel_service_running; then
        rigel_error "RIGEL D-Bus service is not running. Please start the service first."
        return 1
    fi

    rigel_info "Refactoring code: $file_path"
    rigel_execute_query "CodingAgentRefactorCode" "string:\"$code\"" "string:\"$instructions\"" "string:\"$lang\"" "Refactoring code"
}

rigel_coding_explain() {
    if [ $# -lt 1 ]; then
        rigel_error "Usage: rigel_coding_explain 'path/to/code.py' [language]"
        rigel_info "Example: rigel_coding_explain 'main.py' python"
        return 1
    fi

    local file_path="$1"
    local lang="${2:-python}"

    if [ ! -f "$file_path" ]; then
        rigel_error "File not found: $file_path"
        return 1
    fi

    local code
    code=$(cat "$file_path")

    if ! _rigel_service_running; then
        rigel_error "RIGEL D-Bus service is not running. Please start the service first."
        return 1
    fi

    rigel_info "Explaining code: $file_path"
    rigel_execute_query "CodingAgentExplainCode" "string:\"$code\"" "string:\"$lang\"" "Explaining code"
}

rigel_coding_execute() {
    if [ $# -lt 1 ]; then
        rigel_error "Usage: rigel_coding_execute 'path/to/code.py' ['[\"--arg1\",\"--arg2\"]']"
        rigel_info "Example: rigel_coding_execute 'script.py' '[\"--verbose\"]'"
        return 1
    fi

    local file_path="$1"
    local args_json="${2:-[]}"

    if [ ! -f "$file_path" ]; then
        rigel_error "File not found: $file_path"
        return 1
    fi

    if ! _rigel_service_running; then
        rigel_error "RIGEL D-Bus service is not running. Please start the service first."
        return 1
    fi

    rigel_info "Executing: $file_path"
    rigel_execute_query "CodingAgentExecuteCode" "string:\"$file_path\"" "string:\"$args_json\"" "Executing code"
}

rigel_coding_status() {
    if ! _rigel_service_running; then
        rigel_error "RIGEL D-Bus service is not running. Please start the service first."
        return 1
    fi

    rigel_execute_query "CodingAgentGetStatus" "Retrieving status"
}

rigel_coding_history() {
    local n="${1:-20}"

    if ! _rigel_service_running; then
        rigel_error "RIGEL D-Bus service is not running. Please start the service first."
        return 1
    fi

    rigel_execute_query "CodingAgentGetHistory" "string:$n" "Retrieving history"
}

rigel_coding_launch() {
    if ! _rigel_service_running; then
        rigel_error "RIGEL D-Bus service is not running. Please start the service first."
        return 1
    fi

    rigel_info "Launching coding agent..."
    rigel_execute_query "CodingAgentLaunch" "Launching agent"
}

rigel_coding_close() {
    if ! _rigel_service_running; then
        rigel_error "RIGEL D-Bus service is not running. Please start the service first."
        return 1
    fi

    rigel_info "Closing coding agent..."
    rigel_execute_query "CodingAgentClose" "Closing agent"
}

# ── License ──────────────────────────────────────────────────────────────────
rigel_license() {
    rigel_info "Retrieving RIGEL license information..."

    if ! _rigel_service_running; then
        rigel_error "RIGEL D-Bus service is not running. Please start the service first."
        return 1
    fi

    rigel_execute_query "GetLicenseInfo" "Retrieving license info"
}

# ── Status ───────────────────────────────────────────────────────────────────
rigel_status() {
    rigel_info "Checking RIGEL service status..."

    if ! command -v dbus-send >/dev/null 2>&1; then
        rigel_error "dbus-send not found. Install the dbus package."
        return 1
    fi

    if _rigel_service_running; then
        rigel_success "RIGEL D-Bus service is active and registered"

        if timeout 120 dbus-send --system --dest=com.rigel.RigelService \
            --type=method_call --print-reply --reply-timeout=120000 \
            /com/rigel/RigelService com.rigel.RigelService.GetLicenseInfo >/dev/null 2>&1; then
            rigel_success "RIGEL service is responding to queries"
            rigel_info "All systems operational"
        else
            rigel_warn "RIGEL service is registered but not responding properly"
            return 1
        fi
    else
        rigel_error "RIGEL D-Bus service is not registered or running"
        rigel_info "Please start the RIGEL service to enable intelligent functions"
        return 1
    fi
}

# ── Debug / Diagnostics ──────────────────────────────────────────────────────
rigel_debug() {
    rigel_info "Running RIGEL D-Bus diagnostics..."

    if ! command -v dbus-send >/dev/null 2>&1; then
        rigel_error "dbus-send command not found. Please install dbus package."
        return 1
    fi

    if [ -z "$DBUS_SESSION_BUS_ADDRESS" ]; then
        rigel_warn "DBUS_SESSION_BUS_ADDRESS not set"
    else
        rigel_info "D-Bus session address: $DBUS_SESSION_BUS_ADDRESS"
    fi

    rigel_info "Checking RIGEL service availability..."
    if _rigel_service_running; then
        rigel_success "RIGEL D-Bus service is registered"

        rigel_info "Testing basic D-Bus communication..."
        local test_response
        test_response=$(timeout 120 dbus-send --system \
            --dest=com.rigel.RigelService \
            --type=method_call \
            --print-reply \
            --reply-timeout=120000 \
            /com/rigel/RigelService \
            com.rigel.RigelService.GetLicenseInfo 2>&1)

        if [ $? -eq 0 ]; then
            rigel_success "D-Bus communication test successful"
            echo "$test_response" | head -5
        else
            rigel_error "D-Bus communication test failed"
            echo "$test_response"
        fi
    else
        rigel_error "RIGEL D-Bus service is not registered"
        rigel_info "Available D-Bus services:"
        dbus-send --system --dest=org.freedesktop.DBus --type=method_call --print-reply \
            /org/freedesktop/DBus org.freedesktop.DBus.ListNames 2>/dev/null | \
            grep -E 'string "com\.|string "org\.' | head -10
    fi
}

# ── Help ─────────────────────────────────────────────────────────────────────
rigel_help() {
    if [[ -n "$ZSH_VERSION" ]]; then
        print -P "${_rigel_color_cyan}RIGEL Runtime — Intelligent Functions${_rigel_color_reset}"
        print -P ""
        print -P "${_rigel_color_green}Basic Functions:${_rigel_color_reset}"
        print -P "  ${_rigel_color_yellow}rigel_query${_rigel_color_reset} [--no_animate] 'question' — Ask RIGEL a question"
        print -P "  ${_rigel_color_yellow}rigel_memory${_rigel_color_reset} 'id' 'question'          — Ask with conversation memory"
        print -P "  ${_rigel_color_yellow}rigel_think${_rigel_color_reset} 'question'              — Think/reason before answering"
        print -P "  ${_rigel_color_yellow}rigel_tools${_rigel_color_reset} 'task'                    — Use RIGEL with MCP tools"
        print -P "  ${_rigel_color_yellow}rigel_natural_language${_rigel_color_reset} [id] 'request' — Memory-first natural language flow"
        print -P "  ${_rigel_color_yellow}rigel_nl${_rigel_color_reset} [id] 'request'               — Short alias for rigel_natural_language"
        print -P ""
        print -P "${_rigel_color_green}Voice Functions:${_rigel_color_reset}"
        print -P "  ${_rigel_color_yellow}rigel_speak${_rigel_color_reset} 'text' [mode] [voice] — Text-to-speech synthesis"
        print -P "  ${_rigel_color_yellow}rigel_transcribe${_rigel_color_reset} '/path' [model]   — Audio-to-text transcription"
        print -P "  ${_rigel_color_yellow}rigel_voice_list${_rigel_color_reset}                     — List available voices"
        print -P "  ${_rigel_color_yellow}rigel_voice_set${_rigel_color_reset} 'name'            — Switch TTS voice"
        print -P "  ${_rigel_color_yellow}rigel_voice_clone${_rigel_color_reset} 'mp3' 'name'   — Clone a voice from audio"
        print -P "  ${_rigel_color_yellow}rigel_live_transcribe${_rigel_color_reset} start|stop|status — Live voice recognition"
        print -P ""
        print -P "${_rigel_color_green}Vision:${_rigel_color_reset}"
        print -P "  ${_rigel_color_yellow}rigel_vision${_rigel_color_reset} 'image.png' [prompt] — Analyze an image"
        print -P ""
        print -P "${_rigel_color_green}Coding Agent (requires RigelClaude enabled):${_rigel_color_reset}"
        print -P "  ${_rigel_color_yellow}rigel_coding_generate${_rigel_color_reset} 'spec' [lang]  — Generate code from spec"
        print -P "  ${_rigel_color_yellow}rigel_coding_review${_rigel_color_reset} 'file' [lang]   — Review code"
        print -P "  ${_rigel_color_yellow}rigel_coding_debug${_rigel_color_reset} 'file' 'err' [lang] — Debug code with error"
        print -P "  ${_rigel_color_yellow}rigel_coding_refactor${_rigel_color_reset} 'file' 'instr' [lang] — Refactor code"
        print -P "  ${_rigel_color_yellow}rigel_coding_explain${_rigel_color_reset} 'file' [lang]  — Explain code"
        print -P "  ${_rigel_color_yellow}rigel_coding_execute${_rigel_color_reset} 'file' [args] — Execute code"
        print -P "  ${_rigel_color_yellow}rigel_coding_status${_rigel_color_reset}                  — Coding agent status"
        print -P "  ${_rigel_color_yellow}rigel_coding_history${_rigel_color_reset} [n]           — Coding agent history"
        print -P "  ${_rigel_color_yellow}rigel_coding_launch${_rigel_color_reset}                  — Launch coding agent"
        print -P "  ${_rigel_color_yellow}rigel_coding_close${_rigel_color_reset}                   — Close coding agent"
        print -P ""
        print -P "${_rigel_color_green}Utility Functions:${_rigel_color_reset}"
        print -P "  ${_rigel_color_yellow}rigel_license${_rigel_color_reset} — Show license info"
        print -P "  ${_rigel_color_yellow}rigel_status${_rigel_color_reset}  — Check service health"
        print -P "  ${_rigel_color_yellow}rigel_debug${_rigel_color_reset}   — Run D-Bus diagnostics"
        print -P "  ${_rigel_color_yellow}rigel_help${_rigel_color_reset}    — Show this help message"
        print -P "  ${_rigel_color_yellow}rigel_config${_rigel_color_reset} — Re-run configuration wizard"
        print -P "  ${_rigel_color_yellow}rigel_update${_rigel_color_reset} — Update RIGEL engine"
        print -P ""
        print -P "${_rigel_color_blue}Examples:${_rigel_color_reset}"
        print -P "  rigel_query 'What is the weather like today?'"
        print -P "  rigel_memory 'chat_001' 'What did we discuss earlier?'"
        print -P "  rigel_think 'Explain the theory of relativity'"
        print -P "  rigel_tools 'Create a Python script to list files'"
        print -P "  rigel_natural_language 'check system load and explain simply'"
        print -P "  rigel_speak 'Hello world' chunk hal"
        print -P "  rigel_transcribe '/home/user/audio.wav' small"
        print -P "  rigel_vision '/tmp/screenshot.png' 'What is on the screen?'"
        print -P ""
        print -P "${_rigel_color_cyan}For more information: https://github.com/Zerone-Laboratories/RIGEL${_rigel_color_reset}"
    else
        echo -e "${_rigel_color_cyan}RIGEL Runtime — Intelligent Functions${_rigel_color_reset}"
        echo ""
        echo -e "${_rigel_color_green}Basic Functions:${_rigel_color_reset}"
        echo "  rigel_query [--no_animate] 'question' — Ask RIGEL a question"
        echo "  rigel_memory 'id' 'question'          — Ask with conversation memory"
        echo "  rigel_think 'question'              — Think/reason before answering"
        echo "  rigel_tools 'task'                    — Use RIGEL with MCP tools"
        echo "  rigel_natural_language [id] 'request' — Memory-first natural language flow"
        echo "  rigel_nl [id] 'request'               — Short alias for rigel_natural_language"
        echo ""
        echo -e "${_rigel_color_green}Voice Functions:${_rigel_color_reset}"
        echo "  rigel_speak 'text' [mode] [voice] — Text-to-speech synthesis"
        echo "  rigel_transcribe '/path' [model]   — Audio-to-text transcription"
        echo "  rigel_voice_list                     — List available voices"
        echo "  rigel_voice_set 'name'            — Switch TTS voice"
        echo "  rigel_voice_clone 'mp3' 'name'   — Clone a voice from audio"
        echo "  rigel_live_transcribe start|stop|status — Live voice recognition"
        echo ""
        echo -e "${_rigel_color_green}Vision:${_rigel_color_reset}"
        echo "  rigel_vision 'image.png' [prompt] — Analyze an image"
        echo ""
        echo -e "${_rigel_color_green}Coding Agent:${_rigel_color_reset}"
        echo "  rigel_coding_* — Generate, review, debug, refactor, explain, execute code"
        echo ""
        echo -e "${_rigel_color_green}Utility:${_rigel_color_reset}"
        echo "  rigel_license — License info  | rigel_status  — Service health"
        echo "  rigel_debug   — D-Bus diagnostics | rigel_help   — This help"
        echo "  rigel_config  — Re-run config wizard | rigel_update — Update RIGEL"
        echo ""
        echo -e "Type 'rigel_help' for more details."
        echo -e "${_rigel_color_cyan}https://github.com/Zerone-Laboratories/RIGEL${_rigel_color_reset}"
    fi
}

# ── Status prompt ────────────────────────────────────────────────────────────
rigel_status_prompt() {
    if _rigel_service_running 2>/dev/null; then
        if [[ -n "$ZSH_VERSION" ]]; then
            echo "%F{black}%K{green} [0] %k%f"
        else
            echo -e "\033[30m\033[42m [0] \033[0m"
        fi
    else
        if [[ -n "$ZSH_VERSION" ]]; then
            echo "%F{white}%K{red} < ! > %k%f"
        else
            echo -e "\033[37m\033[41m < ! > \033[0m"
        fi
    fi
}

# ── Config & Update ──────────────────────────────────────────────────────────
rigel_config() {
    local wizard_path="$_RIGEL_INSTALL_DIR/rigel-config-wizard.py"

    if [[ -f "$wizard_path" ]]; then
        rigel_info "Launching RIGEL configuration wizard..."
        if command -v python3 &>/dev/null; then
            python3 "$wizard_path" "$_RIGEL_INSTALL_DIR"
        elif command -v python &>/dev/null; then
            python "$wizard_path" "$_RIGEL_INSTALL_DIR"
        else
            rigel_error "Python not found. Please edit $_RIGEL_INSTALL_DIR/.env manually."
            return 1
        fi
    else
        rigel_warn "Config wizard not found at $wizard_path"
        rigel_info "Opening .env in editor..."
        "${EDITOR:-nano}" "$_RIGEL_INSTALL_DIR/.env"
    fi

    # Notify about changes
    rigel_info "Configuration updated. Restart RIGEL for changes to take effect:"
    rigel_info "  sudo docker compose -f $_RIGEL_INSTALL_DIR/docker-compose.yml restart"
}

rigel_update() {
    local rigel_dir="$_RIGEL_INSTALL_DIR"

    if [[ ! -d "$rigel_dir" ]]; then
        rigel_error "RIGEL install directory not found: $rigel_dir"
        return 1
    fi

    rigel_info "Updating RIGEL engine from $rigel_dir..."

    if ! command -v docker &>/dev/null; then
        rigel_error "Docker is not installed."
        return 1
    fi

    cd "$rigel_dir" || return 1

    rigel_info "Pulling latest changes..."
    if ! git pull 2>&1; then
        rigel_error "Git pull failed. Check your network or repository state."
        return 1
    fi

    rigel_info "Rebuilding Docker image..."
    if ! docker compose build --build-arg SKIP_PYTHON_DEPS=false 2>&1; then
        rigel_error "Docker build failed. Check the logs above."
        return 1
    fi

    rigel_info "Restarting RIGEL server..."
    if docker compose up -d rigel-server 2>&1; then
        rigel_success "RIGEL engine updated and restarted successfully!"
    else
        rigel_error "Failed to restart RIGEL server. Check logs: docker compose -f $rigel_dir/docker-compose.yml logs"
        return 1
    fi
}

# ── Server type check ────────────────────────────────────────────────────────
_rigel_check_server_type() {
    local env_file="$_RIGEL_INSTALL_DIR/.env"
    if [[ -f "$env_file" ]]; then
        local server_type
        server_type=$(grep -E '^SERVER_TYPE=' "$env_file" 2>/dev/null | cut -d= -f2 | tr -d '"' | tr -d "'")
        if [[ "$server_type" == "web" ]]; then
            return 0  # web-only mode
        fi
    fi
    return 1  # hybrid, dbus, or unknown
}

# ── Startup banner ───────────────────────────────────────────────────────────
_rigel_startup() {
    if [[ -n "$ZSH_VERSION" ]]; then
        print -P "\n${_rigel_color_magenta}╔═══════════════════════════════════════════════════════════════╗${_rigel_color_reset}"
        print -P "${_rigel_color_magenta} ║${_rigel_color_reset}    ${_rigel_color_bold}${_rigel_color_cyan}RIGEL Runtime Shell Integration v2.0${_rigel_color_bold_off}${_rigel_color_reset}${_rigel_color_magenta} ║${_rigel_color_reset}"
        print -P "${_rigel_color_magenta}╚═══════════════════════════════════════════════════════════════╝${_rigel_color_reset}"
    else
        echo ""
        echo -e "${_rigel_color_magenta}=== RIGEL Runtime Shell Integration v2.0 ===${_rigel_color_reset}"
    fi

    if _rigel_service_running 2>/dev/null; then
        rigel_success "RIGEL D-Bus service is active"
        rigel_info "Intelligent Functions and Multi-Agent Systems are available."
        rigel_info "Type 'rigel_help' for detailed usage information."
    else
        rigel_warn "RIGEL D-Bus service is not active."
        rigel_info "Install and start the RIGEL service to enable intelligent functions."
        rigel_info "Guide: https://github.com/Zerone-Laboratories/RIGEL"
        rigel_info "Use 'rigel_debug' to troubleshoot D-Bus connection issues."
    fi

    # Warn if server is web-only (no D-Bus service)
    if _rigel_check_server_type; then
        if [[ -n "$ZSH_VERSION" ]]; then
            print -P "\n${_rigel_color_bold}${_rigel_color_red}⚠ WARNING:${_rigel_color_reset} ${_rigel_color_yellow}Shell commands will not work without the DBus Server!${_rigel_color_reset}"
            print -P "${_rigel_color_dim}  The server is configured as web-only (SERVER_TYPE=web)."
            print -P "  Run ${_rigel_color_yellow}rigel_config${_rigel_color_dim} and select 'hybrid' or 'dbus' to enable shell commands.${_rigel_color_reset}"
        else
            echo -e "\n${_rigel_color_bold}${_rigel_color_red}WARNING:${_rigel_color_reset} ${_rigel_color_yellow}Shell commands will not work without the DBus Server!${_rigel_color_reset}"
            echo -e "${_rigel_color_dim}  The server is configured as web-only (SERVER_TYPE=web)."
            echo -e "  Run rigel_config and select 'hybrid' or 'dbus' to enable shell commands.${_rigel_color_reset}"
        fi
    fi
}

# Show banner in interactive shells only
if [[ $- == *i* ]]; then
    _rigel_startup
fi
RIGELSHELL

    # Fix ownership of integration file
    if [[ -n "$real_user" ]] && [[ "$real_user" != "root" ]]; then
        chown "$real_user":"$(id -gn "$real_user" 2>/dev/null || echo "$real_user")" "$integration_file" 2>/dev/null || true
    fi
    chmod 644 "$integration_file"

    # Back up existing RC file
    local backup_file="${shell_rc}.backup.$(date +%Y%m%d_%H%M%S)"
    cp "$shell_rc" "$backup_file"
    if [[ -n "$real_user" ]] && [[ "$real_user" != "root" ]]; then
        chown "$real_user":"$(id -gn "$real_user" 2>/dev/null || echo "$real_user")" "$backup_file" 2>/dev/null || true
    fi

    # Append source line to RC file
    echo "" >> "$shell_rc"
    echo "# RIGEL Engine shell integration (installed $(date '+%Y-%m-%d %H:%M:%S'))" >> "$shell_rc"
    echo "source $integration_file" >> "$shell_rc"

    echo ""
    info "RIGEL shell integration installed!"
    detail "Backup saved to:   $backup_file"
    detail "Integration file:  $integration_file"
    detail "Added to:          $shell_rc"
    detail "Start a new terminal or run: source $shell_rc"
    detail "Type 'rigel_help' to see available commands."
}

# ─── Main ────────────────────────────────────────────────────────────────────

main() {
    require_root
    # Only show banner on the elevated run (not the initial non-root run)
    if [[ "$_RIGEL_ELEVATED" == "1" ]] || [[ $EUID -eq 0 ]]; then
        banner
    fi
    check_docker
    check_dbus

    # If running from a cloned repo, use current dir
    if [[ -d ".git" ]] && [[ -f "docker-compose.yml" ]]; then
        INSTALL_DIR="$(pwd)"
        info "Using current directory as install target: $INSTALL_DIR"
    else
        clone_repo
    fi

    fix_docker_compose_volumes
    run_config_wizard
    install_dbus_config
    build_docker
    start_docker
    show_post_install
    install_shell_integration
}

main "$@"