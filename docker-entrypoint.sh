#!/bin/bash

# This script runs before the server starts to ensure database is initialized
set -euo pipefail

echo "Initializing RIGEL tools database..."
python -c "from user_tools import init_tools_database; init_tools_database()"

# If explicit command args are provided, treat them as override EXCEPT when
# they match the default DBus server command (we still want DBus setup then).
if [ $# -gt 0 ]; then
  if [ "$1" = "python" ] && [ "${2:-}" = "dbus_server.py" ]; then
    echo "Detected default DBus server command; running with DBus setup."
    # fall through to SERVER_TYPE handling
  else
    echo "Starting with provided command: $*"
    exec "$@"
  fi
fi

# Support both INFERENCE_ENGINE (docs) and DEFAULT_INFERENCE_ENGINE (compose)
ENGINE=${INFERENCE_ENGINE:-${DEFAULT_INFERENCE_ENGINE:-groq}}

# Only manage Ollama locally if expressly using the ollama engine.
if [ "$ENGINE" = "ollama" ]; then
  # Prefer system/host-provided Ollama if available. We only attempt to install
  # inside the container when no binary is present.
  if command -v ollama >/dev/null 2>&1; then
    echo "Ollama binary found at $(which ollama)"
  else
    echo "Ollama binary not found; will not auto-install when a system Ollama may be used."
    echo "Set OLLAMA_HOST to a reachable host (e.g. http://host.docker.internal:11434) or mount /usr/bin/ollama to use host binary."
  fi

  # If targeting a local Ollama endpoint, optionally start it if the binary exists.
  OLLAMA_TARGET=${OLLAMA_HOST:-http://localhost:11434}
  if [[ "$OLLAMA_TARGET" == http://localhost:* || "$OLLAMA_TARGET" == http://127.0.0.1:* ]]; then
    if command -v ollama >/dev/null 2>&1; then
      echo "Using local Ollama endpoint ($OLLAMA_TARGET); starting 'ollama serve' if not running..."
      if ! pgrep -x "ollama" >/dev/null 2>&1; then
        nohup ollama serve >/var/log/ollama.log 2>&1 &
        sleep 5
      else
        echo "ollama already running."
      fi
    else
      echo "Local Ollama requested ($OLLAMA_TARGET) but 'ollama' binary is unavailable in container."
      echo "Mount system ollama (e.g. /usr/bin/ollama) or set OLLAMA_HOST to a remote endpoint."
    fi
  else
    echo "Remote OLLAMA_HOST detected ($OLLAMA_TARGET); not starting local 'ollama serve'."
  fi
fi

# Choose server type if no explicit command provided
# Support both SERVER_TYPE (docs) and RIGEL_SERVER_TYPE (back-compat)
_SERVER_TYPE=${SERVER_TYPE:-${RIGEL_SERVER_TYPE:-}}

start_dbus_and_server() {
  echo "Starting RIGEL DBus server..."
  # Ensure D-Bus runtime dir exists
  if [ ! -d /var/run/dbus ]; then
    echo "Creating /var/run/dbus directory..."
    mkdir -p /var/run/dbus
  fi

  # Install RIGEL system bus policy inside the container if present
  if [ -f /app/rigel-dbus.conf ]; then
    echo "Installing RIGEL D-Bus policy inside container..."
    mkdir -p /etc/dbus-1/system.d
    cp -f /app/rigel-dbus.conf /etc/dbus-1/system.d/rigel-dbus.conf
    chmod 644 /etc/dbus-1/system.d/rigel-dbus.conf
  fi

  # Prefer host system bus if mounted; otherwise start a local daemon.
  HOST_SOCKET="/run/dbus/system_bus_socket"
  LOCAL_SOCKET="/var/run/dbus/system_bus_socket"

  # If DBUS_SYSTEM_BUS_ADDRESS not set, but host socket is mounted, set it.
  if [ -S "$HOST_SOCKET" ] && [ -z "${DBUS_SYSTEM_BUS_ADDRESS:-}" ]; then
    export DBUS_SYSTEM_BUS_ADDRESS="unix:path=$HOST_SOCKET"
    echo "Using host D-Bus system bus at $HOST_SOCKET"
  fi

  # Start a local D-Bus system daemon only if neither host nor local socket is present
  if [ ! -S "$HOST_SOCKET" ] && [ ! -S "$LOCAL_SOCKET" ]; then
    echo "No system bus socket found; starting local D-Bus system daemon..."
    dbus-daemon --system --fork
    sleep 1
  else
    echo "System bus socket detected; not starting local daemon."
  fi

  exec python dbus_server.py
}

case "$_SERVER_TYPE" in
  web|web_server)
    echo "Starting RIGEL web server (single-instance)..."
    exec python web_server.py
    ;;
  web_instanced|instanced)
    echo "Starting RIGEL web server (instanced)..."
    exec python web_server_instanced.py
    ;;
  web_v2|instanced_v2)
    echo "Starting RIGEL web server (instanced v2)..."
    exec python web_server_instanced_v2.py
    ;;
  dbus|dbus_server)
    start_dbus_and_server
    ;;
  "")
    echo "No SERVER_TYPE set; starting default DBus server..."
    start_dbus_and_server
    ;;
  *)
    echo "Unknown SERVER_TYPE='$_SERVER_TYPE'. Starting default DBus server..."
    start_dbus_and_server
    ;;
esac
