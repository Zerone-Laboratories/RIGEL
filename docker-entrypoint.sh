#!/bin/bash

set -euo pipefail

echo "Initializing RIGEL tools database..."
python -c "from user_tools import init_tools_database; init_tools_database()"

ensure_piper() {
  if command -v piper >/dev/null 2>&1; then
    echo "Piper binary found at $(which piper)"
    return
  fi

  PIPER_CACHE_DIR=${PIPER_CACHE_DIR:-/app/.cache/piper}
  mkdir -p "$PIPER_CACHE_DIR"

  CACHED_BIN="$PIPER_CACHE_DIR/piper/piper"
  if [ -f "$CACHED_BIN" ] && [ -x "$CACHED_BIN" ]; then
    ln -sf "$CACHED_BIN" /usr/local/bin/piper
    echo "Using cached Piper binary at $CACHED_BIN"
    return
  fi

  PIPER_VERSION=${PIPER_VERSION:-1.2.0}
  ARCH=$(uname -m)
  case "$ARCH" in
    x86_64) ARCH_CANDIDATES=("x86_64" "amd64" "x64") ;;
    aarch64|arm64) ARCH_CANDIDATES=("aarch64" "arm64") ;;
    armv7l|armv7) ARCH_CANDIDATES=("armv7l" "armv7") ;;
    *)
      echo "Unsupported architecture for automatic Piper install: $ARCH"
      return 1
      ;;
  esac

  echo "Piper binary not found. Attempting download (v${PIPER_VERSION})..."

  VERSION_TAG="$PIPER_VERSION"
  if [[ "$VERSION_TAG" != v* ]]; then
    VERSION_TAG="v${VERSION_TAG}"
  fi

  RELEASE_API_URL="https://api.github.com/repos/rhasspy/piper/releases/tags/${VERSION_TAG}"
  ARCH_CANDIDATES_CSV=$(IFS=,; echo "${ARCH_CANDIDATES[*]}")
  ASSET_URL=$(python - <<PY
import json
import sys
from urllib.request import urlopen, Request

api_url = "${RELEASE_API_URL}"
arch_candidates = [c for c in "${ARCH_CANDIDATES_CSV}".split(",") if c]

try:
    req = Request(api_url, headers={"Accept": "application/vnd.github+json", "User-Agent": "rigel-entrypoint"})
    with urlopen(req, timeout=20) as resp:
        data = json.load(resp)
except Exception:
    print("")
    sys.exit(0)

assets = data.get("assets", [])
best = ""
for asset in assets:
    name = asset.get("name", "").lower()
    url = asset.get("browser_download_url", "")
    if not ((name.endswith(".tar.gz") and "piper" in name and "linux" in name) or name.startswith("piper_")):
        continue
    if "macos" in name or "windows" in name:
        continue
    if any(candidate in name for candidate in arch_candidates):
        best = url
        break

print(best)
PY
)

  if [ -n "$ASSET_URL" ]; then
    echo "Using Piper asset: $ASSET_URL"
    curl -fL "$ASSET_URL" -o /tmp/piper.tar.gz
    tar -xzf /tmp/piper.tar.gz -C "$PIPER_CACHE_DIR"
  else
    echo "Could not resolve Piper asset from release metadata, trying legacy URL patterns..."
    for candidate in "${ARCH_CANDIDATES[@]}"; do
      for pattern in "piper_${candidate}.tar.gz" "piper_linux_${candidate}.tar.gz"; do
        URL="https://github.com/rhasspy/piper/releases/download/${VERSION_TAG}/${pattern}"
        echo "Trying $URL"
        if curl -fL "$URL" -o /tmp/piper.tar.gz; then
          tar -xzf /tmp/piper.tar.gz -C "$PIPER_CACHE_DIR"
          break 2
        fi
      done
    done
  fi

  PIPER_BIN_PATH=$(find "$PIPER_CACHE_DIR" -type f -name piper 2>/dev/null | head -n 1 || true)

  if [ -z "$PIPER_BIN_PATH" ] || [ ! -f "$PIPER_BIN_PATH" ]; then
    echo "Failed to download/install Piper binary"
    return 1
  fi

  chmod +x "$PIPER_BIN_PATH"
  ln -sf "$PIPER_BIN_PATH" /usr/local/bin/piper
  rm -f /tmp/piper.tar.gz
  echo "Piper installed at /usr/local/bin/piper (source: $PIPER_BIN_PATH)"
}

preload_whisper_model() {
  WHISPER_PRELOAD_MODEL=${WHISPER_PRELOAD_MODEL:-tiny}
  WHISPER_CACHE_DIR=${WHISPER_CACHE_DIR:-/app/.cache/whisper}
  if [ -z "${WHISPER_PRELOAD_MODEL}" ] || [ "${WHISPER_PRELOAD_MODEL}" = "none" ]; then
    echo "Whisper preload disabled"
    return
  fi

  mkdir -p "$WHISPER_CACHE_DIR"

  echo "Ensuring Whisper model '${WHISPER_PRELOAD_MODEL}' is available..."
  python - <<PY
import whisper
model_name = "${WHISPER_PRELOAD_MODEL}"
cache_dir = "${WHISPER_CACHE_DIR}"
whisper.load_model(model_name, download_root=cache_dir)
print(f"Whisper model '{model_name}' ready")
PY
}

if [ "${ENABLE_VOICE_FEATURES:-true}" = "true" ]; then
  if [ "${VOICE_BOOTSTRAP_ASYNC:-false}" = "true" ]; then
    (
      ensure_piper || echo "Warning: Piper bootstrap failed; continuing startup."
      preload_whisper_model || echo "Warning: Whisper preload failed; continuing startup."
    ) &
    echo "Voice bootstrap running in background (set VOICE_BOOTSTRAP_ASYNC=false for blocking mode)."
  else
    ensure_piper || echo "Warning: Piper bootstrap failed; continuing startup."
    preload_whisper_model || echo "Warning: Whisper preload failed; continuing startup."
  fi
else
  echo "Voice bootstrap disabled via ENABLE_VOICE_FEATURES=false"
fi

if [ $# -gt 0 ]; then
  if [ "$1" = "python" ] && [ "${2:-}" = "dbus_server.py" ]; then
    echo "Detected default DBus server command; running with DBus setup."
    # fall through to SERVER_TYPE handling
  else
    echo "Starting with provided command: $*"
    exec "$@"
  fi
fi

ENGINE=${INFERENCE_ENGINE:-${DEFAULT_INFERENCE_ENGINE:-groq}}

if [ "$ENGINE" = "ollama" ]; then
  if command -v ollama >/dev/null 2>&1; then
    echo "Ollama binary found at $(which ollama)"
  else
    echo "Ollama binary not found; will not auto-install when a system Ollama may be used."
    echo "Set OLLAMA_HOST to a reachable host (e.g. http://host.docker.internal:11434) or mount /usr/bin/ollama to use host binary."
  fi

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

configure_dbus_runtime() {
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
}

start_dbus_and_server() {
  echo "Starting RIGEL DBus server..."
  configure_dbus_runtime

  exec python dbus_server.py
}

start_hybrid_servers() {
  echo "Starting RIGEL hybrid mode (Web + DBus servers)..."
  configure_dbus_runtime

  python dbus_server.py &
  DBUS_PID=$!
  echo "DBus server started (pid: ${DBUS_PID})"

  python web_server.py &
  WEB_PID=$!
  echo "Web server started (pid: ${WEB_PID})"

  terminate_children() {
    echo "Stopping hybrid servers..."
    kill "$DBUS_PID" "$WEB_PID" 2>/dev/null || true
    wait "$DBUS_PID" "$WEB_PID" 2>/dev/null || true
  }

  trap terminate_children INT TERM EXIT

  wait -n "$DBUS_PID" "$WEB_PID"
  EXIT_CODE=$?

  if kill -0 "$DBUS_PID" 2>/dev/null || kill -0 "$WEB_PID" 2>/dev/null; then
    echo "One hybrid server exited; shutting down the other..."
    terminate_children
  fi

  trap - INT TERM EXIT
  return "$EXIT_CODE"
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
  hybrid|web_dbus)
    start_hybrid_servers
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
