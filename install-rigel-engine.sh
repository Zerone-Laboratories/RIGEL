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

INSTALL_DIR = Path(sys.argv[1])
ENV_FILE = INSTALL_DIR / ".env"

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.text import Text
from rich import box

console = Console()

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

    "$PYTHON" "$_WIZARD_PY" "$INSTALL_DIR"
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
    read -rp "Choice [1-2]: " engine_choice
    case "$engine_choice" in
        1) ENGINE="groq" ;;
        2) ENGINE="ollama" ;;
        *) ENGINE="groq" ;;
    esac

    read -rp "Enter model name (default: depends on engine): " MODEL
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
}

main "$@"
