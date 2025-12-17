#!/bin/bash

# This script runs before the server starts to ensure database is initialized
set -euo pipefail

echo "Initializing RIGEL tools database..."
python -c "from user_tools import init_tools_database; init_tools_database()"

# Optionally start Ollama if selected as inference engine
# Support both INFERENCE_ENGINE (docs) and DEFAULT_INFERENCE_ENGINE (compose)
ENGINE=${INFERENCE_ENGINE:-${DEFAULT_INFERENCE_ENGINE:-groq}}
if [ "$ENGINE" = "ollama" ]; then
  echo "DEFAULT_INFERENCE_ENGINE=ollama; starting ollama serve in background..."
  # Start ollama in background if not already running
  if ! pgrep -x "ollama" >/dev/null 2>&1; then
    nohup ollama serve >/var/log/ollama.log 2>&1 &
    sleep 5
  else
    echo "ollama already running."
  fi
fi

# Choose server type
# Support both SERVER_TYPE (docs) and RIGEL_SERVER_TYPE (back-compat)
_SERVER_TYPE=${SERVER_TYPE:-${RIGEL_SERVER_TYPE:-}}

if [ -n "$_SERVER_TYPE" ]; then
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
      echo "Starting RIGEL DBus server..."
      # Start D-Bus daemon if not already running
      if [ ! -d /var/run/dbus ]; then
        echo "Creating /var/run/dbus directory..."
        mkdir -p /var/run/dbus
      fi
      if [ ! -S /var/run/dbus/system_bus_socket ]; then
        echo "Starting D-Bus system daemon..."
        dbus-daemon --system --fork
        sleep 1
      else
        echo "D-Bus system daemon already running."
      fi
      exec python dbus_server.py
      ;;
    *)
      echo "Unknown SERVER_TYPE='$_SERVER_TYPE'. Falling back to provided command or default."
      ;;
  esac
fi

# Fallback: if server type not specified, honor provided command args
if [ $# -gt 0 ]; then
  echo "Starting with provided command: $*"
  exec "$@"
else
  echo "No SERVER_TYPE set and no command provided. Starting default DBus server..."
  # Start D-Bus daemon if not already running
  if [ ! -d /var/run/dbus ]; then
    echo "Creating /var/run/dbus directory..."
    mkdir -p /var/run/dbus
  fi
  if [ ! -S /var/run/dbus/system_bus_socket ]; then
    echo "Starting D-Bus system daemon..."
    dbus-daemon --system --fork
    sleep 1
  else
    echo "D-Bus system daemon already running."
  fi
  exec python dbus_server.py
fi
