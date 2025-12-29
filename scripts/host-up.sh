#!/usr/bin/env bash
set -Eeuo pipefail

# Start the Rigel MCP tools server on the host, then run docker compose up
# Only brings up the main rigel-server container to avoid duplicating the tools server in Docker.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
cd "$ROOT_DIR"

VENV_DIR=".venv"
REQ_FILE="requirements.txt"
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
  if command -v python3 >/dev/null 2>&1; then
    PY=python3
  elif command -v python >/dev/null 2>&1; then
    PY=python
  else
    err "Python is not installed or not in PATH. Please install Python 3."
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

  # Install requirements only if needed (checksum memoization)
  local req_hash_file="$VENV_DIR/.requirements.sha256"
  local current_hash
  current_hash=$(sha256sum "$REQ_FILE" | awk '{print $1}')
  if [[ ! -f "$req_hash_file" ]] || [[ "$current_hash" != "$(cat "$req_hash_file" 2>/dev/null || echo)" ]]; then
    info "Installing/updating Python dependencies"
    pip install --upgrade pip >/dev/null
    pip install -r "$REQ_FILE"
    echo "$current_hash" > "$req_hash_file"
  fi
}

check_port_free() {
  # Try to bind a socket using Python to confirm the port is free
  if "$PY" - <<'PY' "$PORT" >/dev/null 2>&1; then exit 0; else exit 1; fi
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

main() {
  ensure_python
  ensure_venv

  trap 'stop_mcp_server' EXIT INT TERM
  start_mcp_server

  info "Bringing up Docker services (excluding rigel-tools-server)"
  info "Run logs: tail -f $LOG_FILE"

  # Only start the main service so the tools server runs on host, not in Docker
  docker compose up rigel-server
}

main "$@"

