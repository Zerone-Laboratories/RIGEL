#!/usr/bin/env bash
set -Eeuo pipefail

# Require elevated privileges for host operations
# if [[ $(id -u) -ne 0 ]]; then
#   echo "[host-up][ERROR] This script must be run with sudo or as root."
#   echo "Run: sudo $0 $*"
#   exit 1
# fi

# Start the Rigel MCP tools server on the host, then run docker compose up
# Only brings up the main rigel-server container to avoid duplicating the tools server in Docker.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
cd "$ROOT_DIR"

VENV_DIR=".venv"
# Use minimal dependencies for host MCP tool server by default
REQ_FILE="requirements-mcp.txt"
PID_FILE=".mcp_server.pid"
LOG_FILE="rigel_tools_server.log"
PORT="8001"

info() { echo "[host-up] $*"; }
err() { echo "[host-up][ERROR] $*" >&2; }

# Optionally load .env into this shell so the host server sees env like RIGEL_ADMIN_KEY
if [[ -f .env ]]; then
  info "Loading environment from .env"
  set -a
  # shellcheck disable=SC1091
  source .env || true
  set +a
fi

ensure_python() {
  if command -v python3.10 >/dev/null 2>&1; then
    PY=python3.10
  elif command -v /usr/bin/python3.10 >/dev/null 2>&1; then
    PY=/usr/bin/python3.10
  elif command -v python3 >/dev/null 2>&1; then
    PY=python3
  elif command -v python >/dev/null 2>&1; then
    PY=python
  else
    err "Python is not installed or not in PATH. Please install Python 3.10."
    exit 1
  fi
}

ensure_venv() {
  if [[ ! -d "$VENV_DIR" ]]; then
    info "Creating virtual environment in $VENV_DIR"
    "$PY" -m venv "$VENV_DIR"
  fi
  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"
  # Ensure we use venv Python for running and installing packages
  PY="$VENV_DIR/bin/python"
  PIP="$VENV_DIR/bin/pip"

  # If rustup was used to install Rust, ensure cargo is on PATH for this shell
  if [[ -f "/root/.cargo/env" ]]; then
    # shellcheck disable=SC1091
    source "/root/.cargo/env"
  elif [[ -f "$HOME/.cargo/env" ]]; then
    # shellcheck disable=SC1091
    source "$HOME/.cargo/env"
  fi

  # Ensure default rust toolchain exists for metadata builds
  if command -v rustup >/dev/null 2>&1; then
    rustup default stable || true
  fi

  # Install requirements only if needed (checksum memoization)
  local req_hash_file="$VENV_DIR/.requirements.sha256"
  local current_hash
  current_hash=$(sha256sum "$REQ_FILE" | awk '{print $1}')
  if [[ ! -f "$req_hash_file" ]] || [[ "$current_hash" != "$(cat "$req_hash_file" 2>/dev/null || echo)" ]]; then
    info "Installing/updating Python dependencies"
    "$PIP" install --upgrade pip setuptools wheel >/dev/null
    # Prefer binary wheels to avoid source builds that may require Rust/Cargo
    if ! "$PIP" install --prefer-binary -r "$REQ_FILE"; then
      err "Dependency install failed. Ensure Rust/Cargo is installed or pydantic-core wheel is available."
      exit 1
    fi
    echo "$current_hash" > "$req_hash_file"
  fi
}

check_port_free() {
  # Try to bind a socket using Python to confirm the port is free
  if "$PY" - "$PORT" <<'PY' >/dev/null 2>&1
import socket, sys
s=socket.socket()
try:
    s.bind(("0.0.0.0", int(sys.argv[1])))
    s.close()
    sys.exit(0)
except OSError:
    sys.exit(1)
PY
  then
    return 0
  else
    return 1
  fi
}

wait_for_mcp_server() {
  local retries=20
  local count=0
  while [[ $count -lt $retries ]]; do
    if curl -fsS "http://127.0.0.1:$PORT/sse" >/dev/null 2>&1; then
      info "MCP server is ready on port $PORT"
      return 0
    fi
    count=$((count + 1))
    sleep 1
  done
  return 1
}

start_mcp_server() {
  if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE" 2>/dev/null)" 2>/dev/null; then
    info "MCP server already running with PID $(cat "$PID_FILE"). Skipping start."
    return
  fi

  if ! check_port_free; then
    err "Port $PORT is in use. Please stop the process using it or set a different port in core/mcp/rigel_tools_server.py."
    exit 1
  fi

  info "Starting host MCP server on port $PORT"
  : > "$LOG_FILE"  # truncate
  nohup "$PY" core/mcp/rigel_tools_server.py >>"$LOG_FILE" 2>&1 &
  MCP_PID=$!
  echo "$MCP_PID" > "$PID_FILE"

  if ! wait_for_mcp_server; then
    err "Failed to confirm MCP server readiness on http://127.0.0.1:$PORT/sse" >&2
    exit 1
  fi

  info "MCP PID: $MCP_PID (logs: $LOG_FILE)"
}

stop_mcp_server() {
  if [[ -f "$PID_FILE" ]]; then
    local pid
    pid=$(cat "$PID_FILE" 2>/dev/null || true)
    if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
      info "Stopping MCP server PID $pid"
      kill "$pid" 2>/dev/null || true
      wait "$pid" 2>/dev/null || true
    fi
    rm -f "$PID_FILE"
  fi
}

cleanup_old_container() {
  local container_name="rigel-rigel-tools-server-1"
  if docker ps -q -f name="rigel-tools-server" >/dev/null 2>&1; then
    info "Stopping old container: $container_name"
    docker stop "$container_name" >/dev/null 2>&1 || true
  fi
  if docker ps -a -q -f name="rigel-tools-server" >/dev/null 2>&1; then
    info "Removing old container: $container_name"
    docker rm -f "$container_name" >/dev/null 2>&1 || true
  fi
}

main() {
  ensure_python
  ensure_venv

  cleanup_old_container
  trap 'stop_mcp_server' EXIT INT TERM
  start_mcp_server

  info "Bringing up Docker services (excluding rigel-tools-server)"
  info "Run logs: tail -f $LOG_FILE"

  # Only start the main service so the tools server runs on host, not in Docker
  docker compose up rigel-server
}

main "$@"

