# This file is part of RIGEL Engine.
#
# RIGEL Engine is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# RIGEL Engine is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

from typing import List, Dict, Any, Optional, Union
from mcp.server.fastmcp import FastMCP
import subprocess
import os
import sys
import json
import tempfile
import shutil
from datetime import datetime
import platform
import uuid
import re
from urllib.parse import urljoin, urlparse, quote_plus
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from typing import Optional
import time
import html
import pexpect
import time
import re
import signal
import json

# Import OSTools class if it's available
try:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from core.os_tools import OSTools
    os_tools = OSTools()
    OS_TOOLS_AVAILABLE = True
except ImportError:
    print("OSTools module not available. Advanced OS operations will be limited.")
    OS_TOOLS_AVAILABLE = False

mcp = FastMCP("Rigel Tool", port=8001, host="0.0.0.0")

# =============================================================================
# REST API for direct tool calls (used by D-Bus server in Docker)
# =============================================================================
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

TOOL_REGISTRY = {}  # Will be populated after tool definitions

# HELPERS--------------------------------------

def trigger_notification(title: str, message: str):
    try:
        subprocess.run(
            ["notify-send", title, message, "-a", "RIGEL Model Context Protocol"],
            capture_output=True,
            text=True,
            timeout=3
        )
    except Exception as e:
        print(f"Failed to send notification: {e}")

QML_TEMPLATES = {

    # ── YES / NO confirmation dialog ─────────────────────────────────────────
    "confirm": """
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell

FloatingWindow {
    id: win
    title: "{title}"
    implicitWidth: 420
    implicitHeight: 180
    visible: true

    Rectangle {
        anchors.fill: parent
        color: "#012946"
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 16

        Text {
            text: "{title}"
            font.pixelSize: 16
            font.bold: true
            color: "#ffffff"
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
        }
        Text {
            text: "{message}"
            font.pixelSize: 13
            color: "#cccccc"
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: 12
            Button {
                text: "{cancel_label}"
                Layout.fillWidth: true
                onClicked: Qt.exit(0)
            }
            Button {
                text: "{confirm_label}"
                Layout.fillWidth: true
                onClicked: Qt.exit(1)
            }
        }
    }
}
""",

    # ── Single-line text input ────────────────────────────────────────────────
    "input": """
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import Quickshell.Io

FloatingWindow {
    id: win
    title: "{title}"
    implicitWidth: 460
    implicitHeight: 210
    visible: true

    Rectangle {
        anchors.fill: parent
        color: "#012946"
    }

    // Write result to a temp file since Qt.exit() can't carry a string
    Process {
        id: writer
        command: ["bash", "-c", "echo " + JSON.stringify(field.text) + " > /tmp/qs_input_result.txt"]
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 14

        Text {
            text: "{title}"
            font.pixelSize: 16
            font.bold: true
            color: "#ffffff"
            Layout.fillWidth: true
        }
        Text {
            text: "{message}"
            font.pixelSize: 13
            color: "#cccccc"
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
        }
        TextField {
            id: field
            placeholderText: "{placeholder}"
            Layout.fillWidth: true
            echoMode: {echo_mode}
            Keys.onReturnPressed: submit()
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: 12
            Button {
                text: "Cancel"
                Layout.fillWidth: true
                onClicked: Qt.exit(0)
            }
            Button {
                text: "OK"
                Layout.fillWidth: true
                onClicked: submit()
            }
        }
    }

    function submit() {
        writer.running = true
        Qt.exit(1)
    }
}
""",

    # ── Dropdown / option picker ──────────────────────────────────────────────
    "picker": """
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell

FloatingWindow {
    id: win
    title: "{title}"
    implicitWidth: 420
    implicitHeight: 200
    visible: true

    Rectangle {
        anchors.fill: parent
        color: "#012946"
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 14

        Text {
            text: "{title}"
            font.pixelSize: 16
            font.bold: true
            color: "#ffffff"
            Layout.fillWidth: true
        }
        Text {
            text: "{message}"
            font.pixelSize: 13
            color: "#cccccc"
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
        }
        ComboBox {
            id: combo
            model: {options}
            Layout.fillWidth: true
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: 12
            Button {
                text: "Cancel"
                Layout.fillWidth: true
                onClicked: Qt.exit(0)
            }
            Button {
                text: "Select"
                Layout.fillWidth: true
                onClicked: Qt.exit(combo.currentIndex + 1)
            }
        }
    }
}
""",

    # ── Toast / passive notification (auto-dismisses) ─────────────────────────
    # Uses PanelWindow correctly: anchored to bottom edge, margins push it inward
    "notify": """
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell

PanelWindow {
    id: win
    implicitWidth: 360
    implicitHeight: 90
    color: "transparent"

    // Anchor to bottom center - margins offset from the edge
    anchors {
        bottom: true
    }
    margins {
        bottom: 40
    }

    exclusionMode: ExclusionMode.Ignore

    Rectangle {
        anchors.fill: parent
        radius: 12
        color: "{bg_color}"

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 16
            spacing: 4

            Text {
                text: "{title}"
                font.pixelSize: 14
                font.bold: true
                color: "#ffffff"
            }
            Text {
                text: "{message}"
                font.pixelSize: 12
                color: "#dddddd"
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
            }
        }
    }

    Timer {
        interval: {duration_ms}
        running: true
        onTriggered: Qt.exit(0)
    }
}
""",

    # ── Progress / status window ──────────────────────────────────────────────
    "progress": """
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell

FloatingWindow {
    id: win
    title: "{title}"
    implicitWidth: 420
    implicitHeight: 160
    visible: true

    Rectangle {
        anchors.fill: parent
        color: "#012946"
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 16

        Text {
            text: "{title}"
            font.pixelSize: 16
            font.bold: true
            color: "#ffffff"
            Layout.fillWidth: true
        }
        Text {
            text: "{message}"
            font.pixelSize: 13
            color: "#cccccc"
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
        }
        ProgressBar {
            Layout.fillWidth: true
            value: {progress}
            indeterminate: ({progress} < 0)
        }
    }
}
""",

    # ── Freeform raw QML ──────────────────────────────────────────────────────
    "custom": "{qml_code}",
}


# ── Helper ───────────────────────────────────────────────────────────────────

def _fill_template(template: str, placeholders: Dict[str, str]) -> str:
    """Fill placeholders in a QML template string."""
    for key, value in placeholders.items():
        template = template.replace("{" + key + "}", str(value))
    return template


def _sanitize_qml(qml: str) -> str:
    """Apply minimal fixes to common QML template mistakes.

    - Replace bare `start()` statements inside item bodies (e.g., Timer) with
      a declarative property `running: true` to avoid parse errors like
      "Expected token ':'".

    This sanitizer is intentionally conservative and line-oriented to avoid
    changing user intent in custom QML.
    """
    try:
        import re as _re
        # Replace lines that are just `start()` (optionally with spaces/semicolon)
        qml = _re.sub(r"(?m)^[ \t]*start\(\)[ \t]*;?[ \t]*$", "    running: true", qml)
        return qml
    except Exception:
        # If anything goes wrong, return original QML unmodified
        return qml


def _write_qml(qml: str) -> str:
    """Write QML to a temp file and return its path."""
    f = tempfile.NamedTemporaryFile(
        mode="w", suffix=".qml", prefix="mcp_gui_",
        delete=False, dir="/tmp"
    )
    f.write(qml)
    f.flush()
    f.close()
    return f.name

#-------------------------

class ToolCallHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress default logging

    def do_POST(self):
        if self.path == '/call-tool':
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            try:
                data = json.loads(body)
                tool_name = data.get('name')
                arguments = data.get('arguments', {})

                if tool_name in TOOL_REGISTRY:
                    result = TOOL_REGISTRY[tool_name](**arguments)
                    try:
                        message = json.dumps(result)
                    except Exception:
                        message = str(result)
                    if len(message) > 250:
                        message = message[:247] + "..."
                    trigger_notification(f"RIGEL Called: {tool_name}", message)
                    response = json.dumps({"content": [{"type": "text", "text": json.dumps(result)}]})
                    self.send_response(200)
                else:
                    response = json.dumps({"error": f"Tool '{tool_name}' not found"})
                    self.send_response(404)

                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(response.encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

    def do_GET(self):
        if self.path == '/tools':
            trigger_notification("RIGEL Tool List Requested", "Rigel made a request to list all available tools.")
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"tools": list(TOOL_REGISTRY.keys())}).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

def start_rest_api(port=8002):
    server = HTTPServer(('0.0.0.0', port), ToolCallHandler)
    print(f"REST API for tool calls running on http://0.0.0.0:{port}")
    server.serve_forever()


@mcp.tool()
def current_time() -> Dict[str, Any]:
    """Returns the current time."""
    _tool_result = {"time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    try:
        _tool_message = json.dumps(_tool_result)
    except Exception:
        _tool_message = str(_tool_result)
    if len(_tool_message) > 250:
        _tool_message = _tool_message[:247] + '...'
    trigger_notification(f'Tool executed: current_time', _tool_message)
    return _tool_result

@mcp.tool()
def show_available_commands() -> Dict[str, Any]:
    """Returns all available bash builtin commands (from `help`)"""
    print("HIT TOOL LISTS")
    result = subprocess.run(
        ["bash", "-lc", "help"],
        capture_output=True,
        text=True
    )

    print(result)

    commands = []
    for line in result.stdout.splitlines():
        if line.startswith("  "):
            cmd = line.strip().split()[0]
            commands.append(cmd)

    _tool_result = {
        "count": len(commands),
        "commands": sorted(set(commands))
    }
    try:
        _tool_message = json.dumps(_tool_result)
    except Exception:
        _tool_message = str(_tool_result)
    if len(_tool_message) > 250:
        _tool_message = _tool_message[:247] + '...'
    trigger_notification(f'Tool executed: show_available_commands', _tool_message)
    return _tool_result

@mcp.tool()
def create_file(directory, file_name) -> Dict[str, Any]:
    """
    Create a file in a specific directory
    eg: create_file("/home/data", "file.ext")
    """
    try:
        output = subprocess.run(["touch", f"{directory}/{file_name}"])
        _tool_result = {"output": f"{output}"}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: create_file', _tool_message)
        return _tool_result
    except:
        _tool_result = {"output": "Failed to create file"}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: create_file', _tool_message)
        return _tool_result

@mcp.tool()
def create_folder(folder_location_and_name) -> Dict[str, Any]:
    """
    Create a folder/directory in a provided location
    eg: create_folder("/path/to/directory)
    """
    try:
        output = subprocess.run(["mkdir", f"{folder_location_and_name}"])
        _tool_result = {"output": f"{output}"}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: create_folder', _tool_message)
        return _tool_result
    except:
        _tool_result = {"output": "Failed to create file"}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: create_folder', _tool_message)
        return _tool_result



@mcp.tool()
def find_executable(app_name: str) -> Dict[str, Any]:
    """Find the path to an executable"""
    try:
        result = subprocess.run(
            ["dbus-send", "--system", "--dest=org.rigel.OSControl",
             "--type=method_call", "/org/rigel/OSControl",
             "org.rigel.OSControl.FindExecutable", f"string:'{app_name}'"],
            capture_output=True, text=True
        )
        output = result.stdout.strip()
        _tool_result = {"executable": output}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: find_executable', _tool_message)
        return _tool_result
    except Exception as e:
        _tool_result = {"error": str(e)}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: find_executable', _tool_message)
        return _tool_result


@mcp.tool()
def start_application(app_name: str) -> Dict[str, Any]:
    """Start a program"""
    try:
        result = subprocess.run(
            ["dbus-send", "--system", "--print-reply",
             "--dest=org.rigel.OSControl", "/org/rigel/OSControl",
             "org.rigel.OSControl.StartApplication", f"string:'{app_name}'"],
            capture_output=True, text=True
        )
        output = result.stdout.strip()
        _tool_result = {"output": output}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: start_application', _tool_message)
        return _tool_result
    except Exception as e:
        _tool_result = {"error": str(e)}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: start_application', _tool_message)
        return _tool_result


@mcp.tool()
def get_pids(app_name: str) -> Dict[str, Any]:
    """Get the PIDs of a running program"""
    try:
        result = subprocess.run(
            ["dbus-send", "--system", "--print-reply",
             "--dest=org.rigel.OSControl", "/org/rigel/OSControl",
             "org.rigel.OSControl.GetPids", f"string:'{app_name}'"],
            capture_output=True, text=True
        )
        pids = result
        print(result)
        _tool_result = {"output": str(pids)}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: get_pids', _tool_message)
        return _tool_result
    except Exception as e:
        _tool_result = {"error": str(e)}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: get_pids', _tool_message)
        return _tool_result


@mcp.tool()
def kill_application(app_name: str) -> Dict[str, Any]:
    """Kill a program"""
    try:
        result = subprocess.run(
            ["dbus-send", "--system", "--print-reply",
             "--dest=org.rigel.OSControl", "/org/rigel/OSControl",
             "org.rigel.OSControl.KillApplication", f"string:'{app_name}'"],
            capture_output=True, text=True
        )
        output = result.stdout.strip()
        _tool_result = {"output": output}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: kill_application', _tool_message)
        return _tool_result
    except Exception as e:
        _tool_result = {"error": str(e)}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: kill_application', _tool_message)
        return _tool_result


@mcp.tool()
def kill_pid(pid: int) -> Dict[str, Any]:
    """Kill a specific program from PID"""
    try:
        result = subprocess.run(
            ["dbus-send", "--system", "--print-reply",
             "--dest=org.rigel.OSControl", "/org/rigel/OSControl",
             "org.rigel.OSControl.KillPid", f"int32:{pid}"],
            capture_output=True, text=True
        )
        output = result.stdout.strip()
        _tool_result = {"output": output}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: kill_pid', _tool_message)
        return _tool_result
    except Exception as e:
        _tool_result = {"error": str(e)}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: kill_pid', _tool_message)
        return _tool_result


def _find_active_session_bus() -> Optional[Dict[str, str]]:
    """Return the env values for the first active user session, if available."""
    try:
        sessions = subprocess.check_output(
            ["loginctl", "list-sessions", "--no-legend", "--no-pager"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip().splitlines()

        for line in sessions:
            session_id = line.split()[0] if line.strip() else None
            if not session_id:
                continue

            try:
                active_prop = subprocess.check_output(
                    ["loginctl", "show-session", session_id, "-p", "Active"],
                    text=True,
                    stderr=subprocess.DEVNULL,
                ).strip()
                if "=" not in active_prop:
                    continue
                _, active = active_prop.split("=", 1)
                if active.strip().lower() != "yes":
                    continue
            except Exception:
                continue

            props = subprocess.check_output(
                ["loginctl", "show-session", session_id,
                 "-p", "DBUS_SESSION_BUS_ADDRESS",
                 "-p", "XDG_RUNTIME_DIR",
                 "-p", "DISPLAY",
                 "-p", "XDG_SESSION_TYPE",
                 "-p", "Name"],
                text=True,
                stderr=subprocess.DEVNULL,
            )
            env = {}
            for p in props.strip().splitlines():
                if "=" in p:
                    k, v = p.split("=", 1)
                    env[k] = v

            if env.get("DBUS_SESSION_BUS_ADDRESS"):
                # add or preserve username from session line
                parts = line.split()
                if len(parts) >= 3:
                    env["USER"] = parts[2]
                return env

    except Exception:
        pass
    return None

@mcp.tool()
def send_dbus_notification(title: str, message: str) -> Dict[str, Any]:
    """Send a desktop notification using notify-send via D-Bus."""
    import subprocess
    import shutil


    try:
        result = subprocess.run(
            ["notify-send", title, message],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            _tool_result = {
                "success": True,
                "title": title,
                "message": message
            }
            try:
                _tool_message = json.dumps(_tool_result)
            except Exception:
                _tool_message = str(_tool_result)
            if len(_tool_message) > 250:
                _tool_message = _tool_message[:247] + '...'
            trigger_notification(f'Tool executed: send_dbus_notification', _tool_message)
            return _tool_result
        else:
            _tool_result = {
                "success": False,
                "error": result.stderr.strip() or "notify-send exited with non-zero status",
                "returncode": result.returncode
            }
            try:
                _tool_message = json.dumps(_tool_result)
            except Exception:
                _tool_message = str(_tool_result)
            if len(_tool_message) > 250:
                _tool_message = _tool_message[:247] + '...'
            trigger_notification(f'Tool executed: send_dbus_notification', _tool_message)
            return _tool_result

    except subprocess.TimeoutExpired:
        _tool_result = {"success": False, "error": "notify-send timed out"}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: send_dbus_notification', _tool_message)
        return _tool_result
    except Exception as e:
        _tool_result = {"success": False, "error": str(e)}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: send_dbus_notification', _tool_message)
        return _tool_result


def get_system_specs() -> Dict[str, Any]:
    """Get basic system specifications"""
    try:
        specs = {
            "os": platform.system(),
            "os_version": platform.version(),
            "architecture": platform.machine(),
            "cpu": platform.processor(),
            "python_version": platform.python_version(),
            "PCI-EXPRESS": subprocess.run(["lspci"], capture_output=True, text=True).stdout.strip()
        }
        return {"success": True, "specs": specs}
    except Exception as e:
        return {"success": False, "error": str(e)}

def check_usb_devices() -> Dict[str, Any]:
    """Check connected USB devices"""
    try:
        result = subprocess.run(["lsusb"], capture_output=True, text=True)
        devices = []
        for line in result.stdout.strip().splitlines():
            parts = line.split()
            if len(parts) >= 6:
                bus = parts[1]
                device = parts[3].rstrip(":")
                id_vendor, id_product = parts[5].split(":")
                description = " ".join(parts[6:])
                devices.append({
                    "bus": bus,
                    "device": device,
                    "id_vendor": id_vendor,
                    "id_product": id_product,
                    "description": description
                })
        return {"success": True, "devices": devices}
    except Exception as e:
        return {"success": False, "error": str(e)}

def check_network_status() -> Dict[str, Any]:
    """Check network connectivity and interfaces"""
    try:
        # Check connectivity
        try:
            urlopen("https://www.google.com", timeout=5)
            connectivity = "Online"
        except (URLError, HTTPError):
            connectivity = "Offline"

        # Get interfaces
        result = subprocess.run(["ip", "addr"], capture_output=True, text=True)
        interfaces = []
        current_iface = None
        for line in result.stdout.strip().splitlines():
            if re.match(r"^\d+:\s+(\w+):", line):
                if current_iface:
                    interfaces.append(current_iface)
                iface_name = re.findall(r"^\d+:\s+(\w+):", line)[0]
                current_iface = {"name": iface_name, "status": "Down", "ip_addresses": []}
                if "UP" in line:
                    current_iface["status"] = "Up"
            elif current_iface and "inet " in line:
                ip = re.findall(r"inet\s+([\d\.]+)", line)
                if ip:
                    current_iface["ip_addresses"].append(ip[0])

        if current_iface:
            interfaces.append(current_iface)

        return {"success": True, "connectivity": connectivity, "interfaces": interfaces}
    except Exception as e:
        return {"success": False, "error": str(e)}


# =============================================================================
# KDE PLASMA DESKTOP TOOLS
# =============================================================================

@mcp.tool()
def set_volume(level: int, mute: bool = False) -> Dict[str, Any]:
    """
    Set system volume level (0-100) or toggle mute.
    eg: set_volume(50) or set_volume(0, mute=True)
    """
    try:
        if mute:
            result = subprocess.run(
                ["pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle"],
                capture_output=True, text=True
            )
            _tool_result = {"success": True, "action": "toggled mute"}
            try:
                _tool_message = json.dumps(_tool_result)
            except Exception:
                _tool_message = str(_tool_result)
            if len(_tool_message) > 250:
                _tool_message = _tool_message[:247] + '...'
            trigger_notification(f'Tool executed: set_volume', _tool_message)
            return _tool_result
        else:
            level = max(0, min(100, level))
            result = subprocess.run(
                ["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{level}%"],
                capture_output=True, text=True
            )
            _tool_result = {"success": result.returncode == 0, "volume": level}
            try:
                _tool_message = json.dumps(_tool_result)
            except Exception:
                _tool_message = str(_tool_result)
            if len(_tool_message) > 250:
                _tool_message = _tool_message[:247] + '...'
            trigger_notification(f'Tool executed: set_volume', _tool_message)
            return _tool_result
    except Exception as e:
        _tool_result = {"success": False, "error": str(e)}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: set_volume', _tool_message)
        return _tool_result


@mcp.tool()
def get_volume() -> Dict[str, Any]:
    """Get current system volume level and mute status."""
    try:
        result = subprocess.run(
            ["pactl", "get-sink-volume", "@DEFAULT_SINK@"],
            capture_output=True, text=True
        )
        mute_result = subprocess.run(
            ["pactl", "get-sink-mute", "@DEFAULT_SINK@"],
            capture_output=True, text=True
        )
        volume_match = re.search(r"(\d+)%", result.stdout)
        volume = int(volume_match.group(1)) if volume_match else None
        muted = "yes" in mute_result.stdout.lower()
        _tool_result = {"success": True, "volume": volume, "muted": muted}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: get_volume', _tool_message)
        return _tool_result
    except Exception as e:
        _tool_result = {"success": False, "error": str(e)}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: get_volume', _tool_message)
        return _tool_result


@mcp.tool()
def set_brightness(level: int) -> Dict[str, Any]:
    """
    Set screen brightness level (0-100).
    eg: set_brightness(80)
    """
    try:
        level = max(0, min(100, level))
        # Try brightnessctl first, then xrandr fallback
        result = subprocess.run(
            ["brightnessctl", "set", f"{level}%"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            _tool_result = {"success": True, "brightness": level, "method": "brightnessctl"}
            try:
                _tool_message = json.dumps(_tool_result)
            except Exception:
                _tool_message = str(_tool_result)
            if len(_tool_message) > 250:
                _tool_message = _tool_message[:247] + '...'
            trigger_notification(f'Tool executed: set_brightness', _tool_message)
            return _tool_result
        # xrandr fallback
        frac = round(level / 100, 2)
        disp_result = subprocess.run(["xrandr", "--listmonitors"], capture_output=True, text=True)
        display_match = re.search(r"\s+(\S+)$", disp_result.stdout.splitlines()[-1]) if disp_result.stdout.strip() else None
        display = display_match.group(1) if display_match else "eDP-1"
        subprocess.run(["xrandr", "--output", display, "--brightness", str(frac)], capture_output=True)
        _tool_result = {"success": True, "brightness": level, "method": "xrandr"}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: set_brightness', _tool_message)
        return _tool_result
    except Exception as e:
        _tool_result = {"success": False, "error": str(e)}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: set_brightness', _tool_message)
        return _tool_result


@mcp.tool()
def toggle_night_color(enable: bool) -> Dict[str, Any]:
    """
    Enable or disable KDE Night Color (blue light filter).
    eg: toggle_night_color(True)
    """
    try:
        value = "true" if enable else "false"
        subprocess.run([
            "kwriteconfig5", "--file", "kwinrc",
            "--group", "NightColor", "--key", "Active", value
        ], capture_output=True)
        # Reload kwin config to apply
        subprocess.run(["qdbus", "org.kde.KWin", "/KWin", "reconfigure"], capture_output=True)
        _tool_result = {"success": True, "night_color_enabled": enable}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: toggle_night_color', _tool_message)
        return _tool_result
    except Exception as e:
        _tool_result = {"success": False, "error": str(e)}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: toggle_night_color', _tool_message)
        return _tool_result


@mcp.tool()
def toggle_do_not_disturb(enable: bool) -> Dict[str, Any]:
    """
    Enable or disable KDE Do Not Disturb mode (suppresses desktop notifications).
    eg: toggle_do_not_disturb(True)
    """
    try:
        value = "true" if enable else "false"
        subprocess.run([
            "kwriteconfig5", "--file", "plasmanotifyrc",
            "--group", "DoNotDisturb", "--key", "Until", value
        ], capture_output=True)
        # Signal plasmanotify to reload
        subprocess.run([
            "qdbus", "org.kde.plasmashell", "/org/freedesktop/Notifications",
            "org.kde.plasmashell.setInhibited", value
        ], capture_output=True)
        _tool_result = {"success": True, "do_not_disturb": enable}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: toggle_do_not_disturb', _tool_message)
        return _tool_result
    except Exception as e:
        _tool_result = {"success": False, "error": str(e)}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: toggle_do_not_disturb', _tool_message)
        return _tool_result


@mcp.tool()
def toggle_wifi(enable: bool) -> Dict[str, Any]:
    """
    Enable or disable Wi-Fi using nmcli.
    eg: toggle_wifi(False)
    """
    try:
        action = "on" if enable else "off"
        result = subprocess.run(
            ["nmcli", "radio", "wifi", action],
            capture_output=True, text=True
        )
        _tool_result = {"success": result.returncode == 0, "wifi_enabled": enable, "output": result.stdout.strip()}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: toggle_wifi', _tool_message)
        return _tool_result
    except Exception as e:
        _tool_result = {"success": False, "error": str(e)}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: toggle_wifi', _tool_message)
        return _tool_result


@mcp.tool()
def toggle_bluetooth(enable: bool) -> Dict[str, Any]:
    """
    Enable or disable Bluetooth.
    eg: toggle_bluetooth(True)
    """
    try:
        action = "on" if enable else "off"
        result = subprocess.run(
            ["bluetoothctl", "power", action],
            capture_output=True, text=True, timeout=5
        )
        _tool_result = {"success": True, "bluetooth_enabled": enable, "output": result.stdout.strip()}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: toggle_bluetooth', _tool_message)
        return _tool_result
    except Exception as e:
        _tool_result = {"success": False, "error": str(e)}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: toggle_bluetooth', _tool_message)
        return _tool_result


@mcp.tool()
def list_running_apps() -> Dict[str, Any]:
    """
    List all currently running GUI windows and background processes on the KDE desktop.
    """
    try:
        windows = []
        wm_result = subprocess.run(["wmctrl", "-l"], capture_output=True, text=True)
        if wm_result.returncode == 0:
            for line in wm_result.stdout.strip().splitlines():
                parts = line.split(None, 3)
                if len(parts) >= 4:
                    windows.append({
                        "window_id": parts[0],
                        "desktop": parts[1],
                        "host": parts[2],
                        "title": parts[3]
                    })
        # Top 50 running processes
        ps_result = subprocess.run(
            ["ps", "-eo", "pid,comm", "--no-headers"],
            capture_output=True, text=True
        )
        processes = []
        for p in ps_result.stdout.strip().splitlines():
            parts = p.split(None, 1)
            if len(parts) == 2:
                processes.append({"pid": parts[0], "name": parts[1]})
        _tool_result = {"success": True, "windows": windows, "processes": processes[:50]}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: list_running_apps', _tool_message)
        return _tool_result
    except Exception as e:
        _tool_result = {"success": False, "error": str(e)}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: list_running_apps', _tool_message)
        return _tool_result


@mcp.tool()
def open_app(app_name: str) -> Dict[str, Any]:
    """
    Open/launch an application by name on KDE Plasma.
    eg: open_app("dolphin"), open_app("firefox"), open_app("konsole")
    """
    try:
        proc = subprocess.Popen(
            [app_name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        _tool_result = {"success": True, "app": app_name, "pid": proc.pid}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: open_app', _tool_message)
        return _tool_result
    except FileNotFoundError:
        # Try via kstart5 for better KDE integration
        try:
            proc = subprocess.Popen(
                ["kstart5", app_name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
            _tool_result = {"success": True, "app": app_name, "pid": proc.pid, "method": "kstart5"}
            try:
                _tool_message = json.dumps(_tool_result)
            except Exception:
                _tool_message = str(_tool_result)
            if len(_tool_message) > 250:
                _tool_message = _tool_message[:247] + '...'
            trigger_notification(f'Tool executed: open_app', _tool_message)
            return _tool_result
        except Exception as e2:
            _tool_result = {"success": False, "error": f"App '{app_name}' not found: {str(e2)}"}
            try:
                _tool_message = json.dumps(_tool_result)
            except Exception:
                _tool_message = str(_tool_result)
            if len(_tool_message) > 250:
                _tool_message = _tool_message[:247] + '...'
            trigger_notification(f'Tool executed: open_app', _tool_message)
            return _tool_result
    except Exception as e:
        _tool_result = {"success": False, "error": str(e)}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: open_app', _tool_message)
        return _tool_result


@mcp.tool()
def close_app_by_name(app_name: str, force: bool = False) -> Dict[str, Any]:
    """
    Close an application gracefully by process name. Use force=True to SIGKILL.
    eg: close_app_by_name("firefox"), close_app_by_name("vlc", force=True)
    """
    try:
        signal_flag = "-9" if force else "-15"
        result = subprocess.run(
            ["pkill", signal_flag, "-f", app_name],
            capture_output=True, text=True
        )
        _tool_result = {
            "success": result.returncode == 0,
            "app": app_name,
            "force": force,
            "output": result.stdout.strip() or ("Killed" if result.returncode == 0 else "Process not found")
        }
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: close_app_by_name', _tool_message)
        return _tool_result
    except Exception as e:
        _tool_result = {"success": False, "error": str(e)}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: close_app_by_name', _tool_message)
        return _tool_result


@mcp.tool()
def close_window_by_title(title: str) -> Dict[str, Any]:
    """
    Close a window gracefully by its title using wmctrl.
    eg: close_window_by_title("Mozilla Firefox")
    """
    try:
        result = subprocess.run(
            ["wmctrl", "-c", title],
            capture_output=True, text=True
        )
        _tool_result = {"success": result.returncode == 0, "title": title}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: close_window_by_title', _tool_message)
        return _tool_result
    except Exception as e:
        _tool_result = {"success": False, "error": str(e)}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: close_window_by_title', _tool_message)
        return _tool_result


@mcp.tool()
def focus_window(title: str) -> Dict[str, Any]:
    """
    Bring a window to the front and focus it by (partial) title.
    eg: focus_window("Konsole")
    """
    try:
        result = subprocess.run(
            ["wmctrl", "-a", title],
            capture_output=True, text=True
        )
        _tool_result = {"success": result.returncode == 0, "title": title}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: focus_window', _tool_message)
        return _tool_result
    except Exception as e:
        _tool_result = {"success": False, "error": str(e)}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: focus_window', _tool_message)
        return _tool_result


@mcp.tool()
def switch_virtual_desktop(desktop_number: int) -> Dict[str, Any]:
    """
    Switch to a specific KDE virtual desktop (1-indexed).
    eg: switch_virtual_desktop(2)
    """
    try:
        result = subprocess.run(
            ["qdbus", "org.kde.KWin", "/KWin",
             "org.kde.KWin.setCurrentDesktop", str(desktop_number)],
            capture_output=True, text=True
        )
        _tool_result = {"success": result.returncode == 0, "desktop": desktop_number}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: switch_virtual_desktop', _tool_message)
        return _tool_result
    except Exception as e:
        _tool_result = {"success": False, "error": str(e)}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: switch_virtual_desktop', _tool_message)
        return _tool_result


@mcp.tool()
def get_clipboard_content() -> Dict[str, Any]:
    """Get the current clipboard text content."""
    try:
        result = subprocess.run(
            ["xclip", "-selection", "clipboard", "-o"],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            result = subprocess.run(["xsel", "--clipboard", "--output"], capture_output=True, text=True)
        _tool_result = {"success": True, "content": result.stdout}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: get_clipboard_content', _tool_message)
        return _tool_result
    except Exception as e:
        _tool_result = {"success": False, "error": str(e)}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: get_clipboard_content', _tool_message)
        return _tool_result


@mcp.tool()
def set_clipboard_content(text: str) -> Dict[str, Any]:
    """
    Copy a text string into the clipboard.
    eg: set_clipboard_content("Hello, world!")
    """
    try:
        result = subprocess.run(
            ["xclip", "-selection", "clipboard"],
            input=text, capture_output=True, text=True
        )
        if result.returncode != 0:
            subprocess.run(["xsel", "--clipboard", "--input"], input=text, text=True)
        _tool_result = {"success": True, "set": text[:80] + ("..." if len(text) > 80 else "")}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: set_clipboard_content', _tool_message)
        return _tool_result
    except Exception as e:
        _tool_result = {"success": False, "error": str(e)}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: set_clipboard_content', _tool_message)
        return _tool_result


@mcp.tool()
def set_wallpaper(image_path: str) -> Dict[str, Any]:
    """
    Set the KDE Plasma desktop wallpaper from a local file path.
    eg: set_wallpaper("/home/user/Pictures/wallpaper.jpg")
    """
    try:
        if not os.path.exists(image_path):
            _tool_result = {"success": False, "error": f"File not found: {image_path}"}
            try:
                _tool_message = json.dumps(_tool_result)
            except Exception:
                _tool_message = str(_tool_result)
            if len(_tool_message) > 250:
                _tool_message = _tool_message[:247] + '...'
            trigger_notification(f'Tool executed: set_wallpaper', _tool_message)
            return _tool_result
        script = f"""
var allDesktops = desktops();
for (var i = 0; i < allDesktops.length; i++) {{
    var d = allDesktops[i];
    d.wallpaperPlugin = "org.kde.image";
    d.currentConfigGroup = ["Wallpaper", "org.kde.image", "General"];
    d.writeConfig("Image", "file://{image_path}");
}}
"""
        result = subprocess.run(
            ["qdbus", "org.kde.plasmashell", "/PlasmaShell",
             "org.kde.PlasmaShell.evaluateScript", script],
            capture_output=True, text=True
        )
        _tool_result = {"success": result.returncode == 0, "wallpaper": image_path}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: set_wallpaper', _tool_message)
        return _tool_result
    except Exception as e:
        _tool_result = {"success": False, "error": str(e)}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: set_wallpaper', _tool_message)
        return _tool_result


@mcp.tool()
def lock_screen() -> Dict[str, Any]:
    """Lock the KDE Plasma screen immediately."""
    try:
        result = subprocess.run(
            ["qdbus", "org.kde.screensaver", "/ScreenSaver",
             "org.freedesktop.ScreenSaver.Lock"],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            subprocess.run(["loginctl", "lock-session"], capture_output=True)
        _tool_result = {"success": True}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: lock_screen', _tool_message)
        return _tool_result
    except Exception as e:
        _tool_result = {"success": False, "error": str(e)}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: lock_screen', _tool_message)
        return _tool_result


@mcp.tool()
def take_screenshot(save_path: str = "/tmp/screenshot.png", with_delay: int = 0) -> Dict[str, Any]:
    """
    Take a screenshot of the full desktop.
    eg: take_screenshot("/home/user/Pictures/snap.png", with_delay=2)
    """
    try:
        # Try spectacle (native KDE tool) first
        cmd = ["spectacle", "-b", "-f", "-o", save_path]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            # Fallback to scrot
            cmd = ["scrot"]
            if with_delay > 0:
                cmd += ["-d", str(with_delay)]
            cmd.append(save_path)
            result = subprocess.run(cmd, capture_output=True, text=True)
        _tool_result = {"success": os.path.exists(save_path), "path": save_path}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: take_screenshot', _tool_message)
        return _tool_result
    except Exception as e:
        _tool_result = {"success": False, "error": str(e)}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: take_screenshot', _tool_message)
        return _tool_result


@mcp.tool()
def run_krunner(query: str) -> Dict[str, Any]:
    """
    Open KRunner with a pre-filled query (KDE's universal launcher/search/calculator).
    eg: run_krunner("= 5+5"), run_krunner("dolphin")
    """
    try:
        result = subprocess.run(
            ["qdbus", "org.kde.krunner", "/App",
             "org.kde.krunner.App.query", query],
            capture_output=True, text=True
        )
        _tool_result = {"success": result.returncode == 0, "query": query, "output": result.stdout.strip()}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: run_krunner', _tool_message)
        return _tool_result
    except Exception as e:
        _tool_result = {"success": False, "error": str(e)}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: run_krunner', _tool_message)
        return _tool_result


@mcp.tool()
def media_control(action: str) -> Dict[str, Any]:
    """
    Control media playback via playerctl: play, pause, next, previous, stop.
    eg: media_control("next")
    """
    valid = {"play", "pause", "next", "previous", "stop"}
    if action not in valid:
        _tool_result = {"success": False, "error": f"Invalid action. Choose from: {valid}"}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: media_control', _tool_message)
        return _tool_result
    try:
        result = subprocess.run(["playerctl", action], capture_output=True, text=True)
        _tool_result = {"success": result.returncode == 0, "action": action}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: media_control', _tool_message)
        return _tool_result
    except Exception as e:
        _tool_result = {"success": False, "error": str(e)}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: media_control', _tool_message)
        return _tool_result

@mcp.tool()
def get_media_info() -> Dict[str, Any]:
    """Get current media information (title, artist, album) from the active MPRIS player.
    """
    command = ["dbus-send --print-reply --dest=org.freedesktop.DBus /org/freedesktop/DBus org.freedesktop.DBus.ListNames | grep org.mpris.MediaPlayer2."]
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        players = []
        for line in result.stdout.strip().splitlines():
            if "org.mpris.MediaPlayer2." in line:
                player_name = line.split('"')[-2]
                players.append(player_name)


        _tool_result = {"success": True, "players": players}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: get_media_info', _tool_message)
        return _tool_result
    except Exception as e:
        _tool_result = {"success": False, "error": str(e)}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: get_media_info', _tool_message)
        return _tool_result

@mcp.tool()
def get_battery_status() -> Dict[str, Any]:
    """Get current battery level, charging status, and time remaining."""
    try:
        result = subprocess.run(
            ["upower", "-i", "/org/freedesktop/UPower/devices/battery_BAT0"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            info = {}
            for line in result.stdout.splitlines():
                if "percentage" in line:
                    info["level"] = line.split()[-1]
                if "state" in line:
                    info["status"] = line.split()[-1]
                if "time to" in line:
                    info["time_remaining"] = line.strip()
            _tool_result = {"success": True, **info}
            try:
                _tool_message = json.dumps(_tool_result)
            except Exception:
                _tool_message = str(_tool_result)
            if len(_tool_message) > 250:
                _tool_message = _tool_message[:247] + '...'
            trigger_notification(f'Tool executed: get_battery_status', _tool_message)
            return _tool_result
        # Fallback: read from /sys
        for bp in ["/sys/class/power_supply/BAT0", "/sys/class/power_supply/BAT1"]:
            if os.path.exists(bp):
                cap = open(f"{bp}/capacity").read().strip()
                status = open(f"{bp}/status").read().strip()
                _tool_result = {"success": True, "level": f"{cap}%", "status": status}
                try:
                    _tool_message = json.dumps(_tool_result)
                except Exception:
                    _tool_message = str(_tool_result)
                if len(_tool_message) > 250:
                    _tool_message = _tool_message[:247] + '...'
                trigger_notification(f'Tool executed: get_battery_status', _tool_message)
                return _tool_result
        _tool_result = {"success": False, "error": "No battery found"}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: get_battery_status', _tool_message)
        return _tool_result
    except Exception as e:
        _tool_result = {"success": False, "error": str(e)}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: get_battery_status', _tool_message)
        return _tool_result


@mcp.tool()
def set_screen_timeout(seconds: int) -> Dict[str, Any]:
    """
    Set the screen idle/blank timeout in seconds. Use 0 to disable.
    eg: set_screen_timeout(300)
    """
    try:
        subprocess.run([
            "kwriteconfig5", "--file", "powermanagementprofilesrc",
            "--group", "AC", "--group", "DimDisplay",
            "--key", "idleTime", str(seconds * 1000)
        ], capture_output=True)
        subprocess.run([
            "qdbus", "org.kde.Solid.PowerManagement",
            "/org/kde/Solid/PowerManagement", "refreshStatus"
        ], capture_output=True)
        _tool_result = {"success": True, "timeout_seconds": seconds}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: set_screen_timeout', _tool_message)
        return _tool_result
    except Exception as e:
        _tool_result = {"success": False, "error": str(e)}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: set_screen_timeout', _tool_message)
        return _tool_result


@mcp.tool()
def get_wifi_networks() -> Dict[str, Any]:
    """
    Scan and list available Wi-Fi networks with signal strength.
    """
    try:
        result = subprocess.run(
            ["nmcli", "-f", "SSID,SIGNAL,SECURITY,IN-USE", "dev", "wifi", "list"],
            capture_output=True, text=True
        )
        networks = []
        lines = result.stdout.strip().splitlines()
        for line in lines[1:]:  # Skip header
            parts = line.split()
            if parts:
                networks.append(line.strip())
        _tool_result = {"success": result.returncode == 0, "networks": networks}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: get_wifi_networks', _tool_message)
        return _tool_result
    except Exception as e:
        _tool_result = {"success": False, "error": str(e)}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: get_wifi_networks', _tool_message)
        return _tool_result


@mcp.tool()
def connect_wifi(ssid: str, password: str = "") -> Dict[str, Any]:
    """
    Connect to a Wi-Fi network by SSID. Provide password for secured networks.
    eg: connect_wifi("MyNetwork", "mypassword")
    """
    try:
        if password:
            result = subprocess.run(
                ["nmcli", "dev", "wifi", "connect", ssid, "password", password],
                capture_output=True, text=True, timeout=30
            )
        else:
            result = subprocess.run(
                ["nmcli", "dev", "wifi", "connect", ssid],
                capture_output=True, text=True, timeout=30
            )
        _tool_result = {
            "success": result.returncode == 0,
            "ssid": ssid,
            "output": result.stdout.strip() or result.stderr.strip()
        }
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: connect_wifi', _tool_message)
        return _tool_result
    except Exception as e:
        _tool_result = {"success": False, "error": str(e)}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: connect_wifi', _tool_message)
        return _tool_result


@mcp.tool()
def open_system_settings(page: str = "") -> Dict[str, Any]:
    """
    Open KDE System Settings, optionally on a specific page.
    eg: open_system_settings("display") or open_system_settings("sound")
    Common pages: display, sound, network, bluetooth, users, appearance, power
    """
    try:
        cmd = ["systemsettings5"]
        if page:
            cmd.append(page)
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        _tool_result = {"success": True, "page": page or "home", "pid": proc.pid}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: open_system_settings', _tool_message)
        return _tool_result
    except Exception as e:
        _tool_result = {"success": False, "error": str(e)}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: open_system_settings', _tool_message)
        return _tool_result


@mcp.tool()
def get_display_info() -> Dict[str, Any]:
    """
    Get current display/monitor information: resolution, refresh rate, connected outputs.
    """
    try:
        result = subprocess.run(["xrandr"], capture_output=True, text=True)
        monitors = []
        current = None
        for line in result.stdout.splitlines():
            conn_match = re.match(r"^(\S+) connected", line)
            if conn_match:
                if current:
                    monitors.append(current)
                current = {"name": conn_match.group(1), "modes": []}
                res_match = re.search(r"(\d+x\d+)\+\d+\+\d+", line)
                if res_match:
                    current["current_resolution"] = res_match.group(1)
            elif current and re.match(r"^\s+\d+x\d+", line):
                parts = line.strip().split()
                if parts:
                    current["modes"].append(parts[0])
        if current:
            monitors.append(current)
        _tool_result = {"success": True, "monitors": monitors}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: get_display_info', _tool_message)
        return _tool_result
    except Exception as e:
        _tool_result = {"success": False, "error": str(e)}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: get_display_info', _tool_message)
        return _tool_result


@mcp.tool()
def set_display_resolution(output: str, resolution: str) -> Dict[str, Any]:
    """
    Set the resolution for a display output.
    eg: set_display_resolution("HDMI-1", "1920x1080")
    Use get_display_info() to see available outputs and resolutions.
    """
    try:
        result = subprocess.run(
            ["xrandr", "--output", output, "--mode", resolution],
            capture_output=True, text=True
        )
        _tool_result = {
            "success": result.returncode == 0,
            "output": output,
            "resolution": resolution,
            "error": result.stderr.strip() if result.returncode != 0 else None
        }
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: set_display_resolution', _tool_message)
        return _tool_result
    except Exception as e:
        _tool_result = {"success": False, "error": str(e)}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: set_display_resolution', _tool_message)
        return _tool_result


@mcp.tool()
def run_bash_command(command: str, timeout: int = 30) -> Dict[str, Any]:
    """
    Run an arbitrary bash shell command and return stdout/stderr.
    Use with caution. eg: run_bash_command("df -h")
    """
    try:
        if "sudo" in command:
            # Initializing GUI Authentication for sudo commands
            def get_gui_sudo_helper():
                for helper in ["pkexec", "gksudo", "kdesudo", "zenity"]:
                    if subprocess.run(["which", helper], capture_output=True).returncode == 0:
                        return helper
                return None

            helper = get_gui_sudo_helper()

            if helper == "zenity":
                # Prompt for password via Zenity dialog
                try:
                    password_proc = subprocess.run(
                        ["zenity", "--password", "--title=Authentication Required"],
                        capture_output=True, text=True, timeout=timeout
                    )
                except subprocess.TimeoutExpired:
                    _tool_result = {"success": False, "error": f"Authentication timed out after {timeout}s"}
                    try:
                        _tool_message = json.dumps(_tool_result)
                    except Exception:
                        _tool_message = str(_tool_result)
                    if len(_tool_message) > 250:
                        _tool_message = _tool_message[:247] + '...'
                    trigger_notification(f'Tool executed: run_bash_command', _tool_message)
                    return _tool_result

                if password_proc.returncode != 0:
                    _tool_result = {"success": False, "error": "Authentication cancelled by user"}
                    try:
                        _tool_message = json.dumps(_tool_result)
                    except Exception:
                        _tool_message = str(_tool_result)
                    if len(_tool_message) > 250:
                        _tool_message = _tool_message[:247] + '...'
                    trigger_notification(f'Tool executed: run_bash_command', _tool_message)
                    return _tool_result

                password = password_proc.stdout.strip()
                result = subprocess.run(
                    command, shell=True,
                    input=password + "\n",
                    capture_output=True, text=True, timeout=timeout,
                    env={**os.environ, "SUDO_ASKPASS": "/bin/false"}
                )

            elif helper in ("pkexec", "gksudo", "kdesudo"):
                # Strip leading 'sudo' and re-wrap with GUI helper
                stripped = command.strip()
                if stripped.startswith("sudo "):
                    stripped = stripped[5:]
                gui_command = f"{helper} {stripped}"
                result = subprocess.run(
                    gui_command, shell=True,
                    capture_output=True, text=True, timeout=timeout
                )

            else:
                # No GUI helper found, fall back to terminal sudo
                result = subprocess.run(
                    command, shell=True,
                    capture_output=True, text=True, timeout=timeout
                )

        else:
            result = subprocess.run(
                command, shell=True,
                capture_output=True, text=True, timeout=timeout
            )

        _tool_result = {
            "success": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip()
        }
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: run_bash_command', _tool_message)
        return _tool_result

    except subprocess.TimeoutExpired:
        _tool_result = {"success": False, "error": f"Command timed out after {timeout}s"}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: run_bash_command', _tool_message)
        return _tool_result
    except Exception as e:
        _tool_result = {"success": False, "error": str(e)}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: run_bash_command', _tool_message)
        return _tool_result

def get_ztos_aci_devices(only_reachable: bool = True) -> List[Dict[str, str]]:
    """Helper to get list of ztOS Auxiliary Compute Interface devices"""
    args = ["kdeconnect-cli", "--list-devices"]
    if only_reachable:
        args.append("--id-only")
    result = subprocess.run(args, capture_output=True, text=True)

    devices = []
    for line in result.stdout.strip().splitlines():
        if "-" in line:
            parts = line.split("-", 1)
            devices.append({
                "id": parts[0].strip(),
                "name": parts[1].strip() if len(parts) > 1 else "Unknown"
            })
    return devices


@mcp.tool()
def ztos_aci_list_devices(only_reachable: bool = True) -> Dict[str, Any]:
    """
    List all ztOS Auxiliary Compute Interface paired devices.
    eg: ztos_aci_list_devices() or ztos_aci_list_devices(only_reachable=False)
    """
    try:
        args = ["kdeconnect-cli", "--list-devices"]
        if only_reachable:
            args.append("--id-only")

        result = subprocess.run(args, capture_output=True, text=True, timeout=10)
        devices = []
        for line in result.stdout.strip().splitlines():
            if line.strip():
                devices.append(line.strip())

        _tool_result = {
            "success": True,
            "devices": devices,
            "count": len(devices)
        }
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: ztos_aci_list_devices', _tool_message)
        return _tool_result
    except subprocess.TimeoutExpired:
        _tool_result = {"success": False, "error": "ztOS Auxiliary Compute Interface timed out"}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: ztos_aci_list_devices', _tool_message)
        return _tool_result
    except FileNotFoundError:
        _tool_result = {"success": False, "error": "ztOS Auxiliary Compute Interface runtime not found. Install kde-connect package."}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: ztos_aci_list_devices', _tool_message)
        return _tool_result
    except Exception as e:
        _tool_result = {"success": False, "error": str(e)}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: ztos_aci_list_devices', _tool_message)
        return _tool_result


@mcp.tool()
def ztos_aci_send_sms(device_id: str, phone_number: str, message: str) -> Dict[str, Any]:
    """
    Send an SMS via a ztOS Auxiliary Compute Interface paired Android device.
    eg: ztos_aci_send_sms("abc123", "+1234567890", "Hello!")
    First find the ID of the device using the `ztos_aci_list_devices` tool.
    And then find the contacts from `ztos_aci_get_contacts` method
    """
    try:
        result = subprocess.run(
            ["kdeconnect-cli", "--device", device_id, "--send-sms", message, "--destination", phone_number],
            capture_output=True, text=True, timeout=15
        )
        _tool_result = {
            "success": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip()
        }
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: ztos_aci_send_sms', _tool_message)
        return _tool_result
    except subprocess.TimeoutExpired:
        _tool_result = {"success": False, "error": "SMS send timed out after 15s"}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: ztos_aci_send_sms', _tool_message)
        return _tool_result
    except Exception as e:
        _tool_result = {"success": False, "error": str(e)}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: ztos_aci_send_sms', _tool_message)
        return _tool_result


@mcp.tool()
def ztos_aci_send_notification(device_id: str, title: str, message: str, app: str = "MCP") -> Dict[str, Any]:
    """
    Send a notification ping to a ztOS Auxiliary Compute Interface device.
    eg: ztos_aci_send_notification("abc123", "Alert", "Server is down!")
    First find the ID of the device using the `ztos_aci_list_devices` tool.
    """
    try:
        result = subprocess.run(
            ["kdeconnect-cli", "--device", device_id, "--ping-msg", f"{title}: {message}"],
            capture_output=True, text=True, timeout=10
        )
        _tool_result = {
            "success": result.returncode == 0,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip()
        }
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: ztos_aci_send_notification', _tool_message)
        return _tool_result
    except subprocess.TimeoutExpired:
        _tool_result = {"success": False, "error": "Notification timed out after 10s"}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: ztos_aci_send_notification', _tool_message)
        return _tool_result
    except Exception as e:
        _tool_result = {"success": False, "error": str(e)}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: ztos_aci_send_notification', _tool_message)
        return _tool_result


@mcp.tool()
def ztos_aci_ring_device(device_id: str) -> Dict[str, Any]:
    """
    Ring a ztOS Auxiliary Compute Interface device to help locate it.
    eg: ztos_aci_ring_device("abc123")
    First find the ID of the device using the `ztos_aci_list_devices` tool.
    """
    try:
        result = subprocess.run(
            ["kdeconnect-cli", "--device", device_id, "--ring"],
            capture_output=True, text=True, timeout=10
        )
        _tool_result = {
            "success": result.returncode == 0,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip()
        }
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: ztos_aci_ring_device', _tool_message)
        return _tool_result
    except subprocess.TimeoutExpired:
        _tool_result = {"success": False, "error": "Ring command timed out after 10s"}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: ztos_aci_ring_device', _tool_message)
        return _tool_result
    except Exception as e:
        _tool_result = {"success": False, "error": str(e)}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: ztos_aci_ring_device', _tool_message)
        return _tool_result


@mcp.tool()
def ztos_aci_send_file(device_id: str, filepath: str) -> Dict[str, Any]:
    """
    Send a file to a ztOS Auxiliary Compute Interface paired device.
    eg: ztos_aci_send_file("abc123", "/home/user/photo.jpg")
    First find the ID of the device using the `ztos_aci_list_devices` tool.
    """
    try:
        if not os.path.exists(filepath):
            _tool_result = {"success": False, "error": f"File not found: {filepath}"}
            try:
                _tool_message = json.dumps(_tool_result)
            except Exception:
                _tool_message = str(_tool_result)
            if len(_tool_message) > 250:
                _tool_message = _tool_message[:247] + '...'
            trigger_notification(f'Tool executed: ztos_aci_send_file', _tool_message)
            return _tool_result

        filesize = os.path.getsize(filepath)
        result = subprocess.run(
            ["kdeconnect-cli", "--device", device_id, "--share", filepath],
            capture_output=True, text=True, timeout=60
        )
        _tool_result = {
            "success": result.returncode == 0,
            "file": filepath,
            "size_bytes": filesize,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip()
        }
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: ztos_aci_send_file', _tool_message)
        return _tool_result
    except subprocess.TimeoutExpired:
        _tool_result = {"success": False, "error": "File transfer timed out after 60s"}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: ztos_aci_send_file', _tool_message)
        return _tool_result
    except Exception as e:
        _tool_result = {"success": False, "error": str(e)}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: ztos_aci_send_file', _tool_message)
        return _tool_result


@mcp.tool()
def ztos_aci_share_url(device_id: str, url: str) -> Dict[str, Any]:
    """
    Share a URL to open on a ztOS Auxiliary Compute Interface paired device.
    eg: ztos_aci_share_url("abc123", "https://example.com")
    First find the ID of the device using the `ztos_aci_list_devices` tool.
    """
    try:
        result = subprocess.run(
            ["kdeconnect-cli", "--device", device_id, "--share", url],
            capture_output=True, text=True, timeout=10
        )
        _tool_result = {
            "success": result.returncode == 0,
            "url": url,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip()
        }
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: ztos_aci_share_url', _tool_message)
        return _tool_result
    except subprocess.TimeoutExpired:
        _tool_result = {"success": False, "error": "Share URL timed out after 10s"}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: ztos_aci_share_url', _tool_message)
        return _tool_result
    except Exception as e:
        _tool_result = {"success": False, "error": str(e)}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: ztos_aci_share_url', _tool_message)
        return _tool_result


@mcp.tool()
def ztos_aci_get_device_info(device_id: str) -> Dict[str, Any]:
    """
    Get detailed info about a specific ztOS Auxiliary Compute Interface device (battery, name, plugins).
    eg: ztos_aci_get_device_info("abc123")
    First find the ID of the device using the `ztos_aci_list_devices` tool.
    """
    try:
        result = subprocess.run(
            ["kdeconnect-cli", "--device", device_id, "--list-available-plugins"],
            capture_output=True, text=True, timeout=10
        )
        battery_result = subprocess.run(
            ["kdeconnect-cli", "--device", device_id, "--battery"],
            capture_output=True, text=True, timeout=10
        )
        _tool_result = {
            "success": result.returncode == 0,
            "device_id": device_id,
            "plugins": result.stdout.strip().splitlines(),
            "battery": battery_result.stdout.strip(),
            "stderr": result.stderr.strip()
        }
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: ztos_aci_get_device_info', _tool_message)
        return _tool_result
    except subprocess.TimeoutExpired:
        _tool_result = {"success": False, "error": "Device info timed out after 10s"}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: ztos_aci_get_device_info', _tool_message)
        return _tool_result
    except Exception as e:
        _tool_result = {"success": False, "error": str(e)}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: ztos_aci_get_device_info', _tool_message)
        return _tool_result


@mcp.tool()
def ztos_aci_run_command(device_id: str, command_name: str) -> Dict[str, Any]:
    """
    Trigger a pre-configured remote command on a ztOS Auxiliary Compute Interface device.
    Commands must be set up in the ztOS Auxiliary Compute Interface app on the device first.
    eg: ztos_aci_run_command("abc123", "lock-screen")
    First find the ID of the device using the `ztos_aci_list_devices` tool.
    """
    try:
        # First list available commands
        list_result = subprocess.run(
            ["kdeconnect-cli", "--device", device_id, "--list-commands"],
            capture_output=True, text=True, timeout=10
        )

        # Find the command key by name
        command_key = None
        for line in list_result.stdout.strip().splitlines():
            if command_name.lower() in line.lower():
                command_key = line.split(":")[0].strip()
                break

        if not command_key:
            _tool_result = {
                "success": False,
                "error": f"Command '{command_name}' not found on device",
                "available_commands": list_result.stdout.strip()
            }
            try:
                _tool_message = json.dumps(_tool_result)
            except Exception:
                _tool_message = str(_tool_result)
            if len(_tool_message) > 250:
                _tool_message = _tool_message[:247] + '...'
            trigger_notification(f'Tool executed: ztos_aci_run_command', _tool_message)
            return _tool_result

        result = subprocess.run(
            ["kdeconnect-cli", "--device", device_id, "--execute-command", command_key],
            capture_output=True, text=True, timeout=15
        )
        _tool_result = {
            "success": result.returncode == 0,
            "command": command_name,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip()
        }
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: ztos_aci_run_command', _tool_message)
        return _tool_result
    except subprocess.TimeoutExpired:
        _tool_result = {"success": False, "error": "Command execution timed out after 15s"}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: ztos_aci_run_command', _tool_message)
        return _tool_result
    except Exception as e:
        _tool_result = {"success": False, "error": str(e)}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: ztos_aci_run_command', _tool_message)
        return _tool_result

@mcp.tool()
def ztos_aci_list_user_contacts() -> Dict[str, Any]:
    """
    Get a list of user's contacts from a ztOS Auxiliary Compute Interface paired device.
    [TODO]
    """
    myContacts = {
        "(My Self)": ""
    }

    _tool_result = {
        "success": True,
        "available contacts": myContacts}
    try:
        _tool_message = json.dumps(_tool_result)
    except Exception:
        _tool_message = str(_tool_result)
    if len(_tool_message) > 250:
        _tool_message = _tool_message[:247] + '...'
    trigger_notification(f'Tool executed: ztos_aci_list_user_contacts', _tool_message)
    return _tool_result


# @mcp.tool()
# def browser_agent_task(task: str, model: str = "gemini-2.5-flash", timeout: int = 120) -> Dict[str, Any]:
#     """
#     Launch an autonomous AI browser agent that controls a real web browser to complete any web-based task.
#     The agent can open websites, click buttons, fill forms, scroll, search, and extract information — just like a human would.

#     Best used for:
#     - Web searches with specific goals  eg: "search duckduckgo for the capital of Japan and return the answer"
#     - Filling and submitting forms      eg: "go to example.com/contact and fill the form with name=John, email=john@x.com"
#     - Extracting structured data        eg: "go to news.ycombinator.com and return the top 5 post titles"
#     - Multi-step web workflows          eg: "go to reddit.com/r/python, find the top post this week, and summarize the comments"
#     - Checking live website content     eg: "go to example.com and tell me what the current price of the Pro plan is"

#     Not suitable for:
#     - Tasks that don't require a browser (use run_bash_command instead)
#     - Downloading large files (may time out)
#     - Sites that require pre-authenticated sessions unless cookies are set up

#     eg: browser_agent_task("use duckduckgo and find the CEO of OpenAI")
#     """
#     try:
#         import asyncio
#         from browser_use import Agent, ChatGoogle
#         from dotenv import load_dotenv
#         load_dotenv()

#         async def run_agent():
#             llm = ChatGoogle(model=model)
#             agent = Agent(task=task, llm=llm)
#             result = await asyncio.wait_for(agent.run(), timeout=timeout)
#             return result

#         # Handle already-running event loops (e.g. Jupyter / some MCP servers)
#         try:
#             loop = asyncio.get_running_loop()
#             import concurrent.futures
#             with concurrent.futures.ThreadPoolExecutor() as pool:
#                 future = pool.submit(asyncio.run, run_agent())
#                 result = future.result(timeout=timeout + 5)
#         except RuntimeError:
#             result = asyncio.run(run_agent())

#         _tool_result = {
#             "success": True,
#             "task": task,
#             "model": model,
#             "result": str(result) if result else "Task completed with no output"
#         }
#         try:
#             _tool_message = json.dumps(_tool_result)
#         except Exception:
#             _tool_message = str(_tool_result)
#         if len(_tool_message) > 250:
#             _tool_message = _tool_message[:247] + '...'
#         trigger_notification(f'Tool executed: browser_agent_task', _tool_message)
#         return _tool_result

#     except asyncio.TimeoutError:
#         _tool_result = {"success": False, "error": f"Browser agent timed out after {timeout}s"}
#         try:
#             _tool_message = json.dumps(_tool_result)
#         except Exception:
#             _tool_message = str(_tool_result)
#         if len(_tool_message) > 250:
#             _tool_message = _tool_message[:247] + '...'
#         trigger_notification(f'Tool executed: browser_agent_task', _tool_message)
#         return _tool_result
#     except ImportError as e:
#         _tool_result = {"success": False, "error": f"Missing dependency: {e}. Run: pip install browser-use langchain-google-genai"}
#         try:
#             _tool_message = json.dumps(_tool_result)
#         except Exception:
#             _tool_message = str(_tool_result)
#         if len(_tool_message) > 250:
#             _tool_message = _tool_message[:247] + '...'
#         trigger_notification(f'Tool executed: browser_agent_task', _tool_message)
#         return _tool_result
#     except Exception as e:
#         _tool_result = {"success": False, "error": str(e)}
#         try:
#             _tool_message = json.dumps(_tool_result)
#         except Exception:
#             _tool_message = str(_tool_result)
#         if len(_tool_message) > 250:
#             _tool_message = _tool_message[:247] + '...'
#         trigger_notification(f'Tool executed: browser_agent_task', _tool_message)
#         return _tool_result

@mcp.tool()
def ztos_aci_set_volume(device_id: str, volume: int) -> Dict[str, Any]:
    """
    Set the volume on a ztOS Auxiliary Compute Interface paired device (0-100).
    eg: ztos_aci_set_volume("abc123", 50)
    First find the ID of the device using the `ztos_aci_list_devices` tool.
    """
    try:
        if not 0 <= volume <= 100:
            _tool_result = {"success": False, "error": "Volume must be between 0 and 100"}
            try:
                _tool_message = json.dumps(_tool_result)
            except Exception:
                _tool_message = str(_tool_result)
            if len(_tool_message) > 250:
                _tool_message = _tool_message[:247] + '...'
            trigger_notification(f'Tool executed: ztos_aci_set_volume', _tool_message)
            return _tool_result

        result = subprocess.run(
            ["kdeconnect-cli", "--device", device_id, "--set-volume", str(volume)],
            capture_output=True, text=True, timeout=10
        )
        _tool_result = {
            "success": result.returncode == 0,
            "volume": volume,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip()
        }
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: ztos_aci_set_volume', _tool_message)
        return _tool_result
    except subprocess.TimeoutExpired:
        _tool_result = {"success": False, "error": "Volume command timed out after 10s"}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: ztos_aci_set_volume', _tool_message)
        return _tool_result
    except Exception as e:
        _tool_result = {"success": False, "error": str(e)}
        try:
            _tool_message = json.dumps(_tool_result)
        except Exception:
            _tool_message = str(_tool_result)
        if len(_tool_message) > 250:
            _tool_message = _tool_message[:247] + '...'
        trigger_notification(f'Tool executed: ztos_aci_set_volume', _tool_message)
        return _tool_result

@mcp.tool()
def search_web(query: str, max_results: int = 5, timeout: int = 30) -> Dict[str, Any]:
    """
    Search the web using DuckDuckGo and return summarized results.
    Tries news search first, falls back to general text search if no news results found.
    Best used for current events, quick lookups, and factual questions.

    Best used for:
    - Current events / breaking news     eg: search_web("latest Python 3.13 release notes")
    - Quick factual lookups              eg: search_web("who is the CEO of NVIDIA")
    - Research with multiple results     eg: search_web("best Linux distros 2024", max_results=5)
    - Checking if something exists       eg: search_web("is there a KDE Connect Windows client")

    Not suitable for:
    - Tasks needing full page content (use browser_agent_task instead)
    - Queries needing login-gated results

    eg: search_web("OpenAI latest news")
    """
    try:
        from ddgs import DDGS
        trigger_notification(f'WebSearch Tool executed with query: {query}', f'search_web, max_results={max_results}, timeout={timeout}')

        with DDGS() as ddgs:
            results = []

            # 1. Try news search first
            try:
                results = list(ddgs.news(query, region="us-en", max_results=max_results))
            except Exception as e:
                pass  # silently fall through to text search

            # 2. Fall back to text search
            if not results:
                try:
                    results = list(ddgs.text(query, region="us-en", max_results=max_results))
                except Exception as e:
                    return {"success": False, "error": f"Both news and text search failed: {e}"}

            if not results:
                return {
                    "success": False,
                    "query": query,
                    "error": "No results found for this query"
                }

            # Normalize results (news and text have slightly different keys)
            formatted = []
            for r in results:
                formatted.append({
                    "title": r.get("title", "No Title"),
                    "snippet": r.get("body", r.get("snippet", "No snippet"))[:400],
                    "url": r.get("url", r.get("href", "No URL")),
                    "source": r.get("source", r.get("publisher", "Unknown")),
                    "date": r.get("date", "Unknown date")
                })

            return {
                "success": True,
                "query": query,
                "result_count": len(formatted),
                "search_type": "news" if results[0].get("source") else "text",
                "results": formatted
            }

    except ImportError:
        return {"success": False, "error": "duckduckgo-search not installed. Run: pip install duckduckgo-search"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@mcp.tool()
def display_interactive_components_for_user(
    template: str,
    placeholders: Dict[str, str],
    mode: str = "blocking",
    timeout: int = 60
) -> Dict[str, Any]:
    trigger_notification(f'GUI Tool executed with template: {template}', f'mode={mode}, timeout={timeout}s, placeholders={placeholders}')
    """
    Spawn a native Quickshell/QML GUI window and optionally wait for user interaction.
    Use this whenever you need to interact with the user visually, get confirmation,
    collect input, show a notification, or launch a live runtime UI.

    SET THE BACKGROUND COLOR TO BLACK

    Templates:
    - "confirm"  → Yes/No dialog. Returns confirmed: true/false
    - "input"    → Text input dialog. Returns user_input: "..."
    - "picker"   → Dropdown selector. Returns selected_index and selected_value
    - "notify"   → Toast notification (auto-dismisses). Fire-and-forget
    - "progress" → Progress/status window. Returns pid so agent can kill it later
    - "custom"   → Agent provides raw QML via placeholders["qml_code"]

    Modes:
    - "blocking"      → Wait for user to interact, return result (confirm/input/picker)
    - "fire_and_forget" → Launch and return immediately (notify/progress/custom apps)

    Placeholders per template:
    - confirm:  title, message, confirm_label (default OK), cancel_label (default Cancel)
    - input:    title, message, placeholder, echo_mode (TextField.Normal / TextField.Password)
    - picker:   title, message, options (as QML array eg '["Option A","Option B"]')
    - notify:   title, message, bg_color (eg "#2d2d2d"), duration_ms (eg "3000")
    - progress: title, message, progress (0.0-1.0 or -1 for indeterminate)
    - custom:   qml_code (full raw QML string)

    eg: display_interactive_components_for_user("confirm", {"title": "Delete file?", "message": "This cannot be undone.", "confirm_label": "Delete", "cancel_label": "Cancel"})
    eg: display_interactive_components_for_user("input",   {"title": "Enter your name", "message": "Used for the report.", "placeholder": "John Doe", "echo_mode": "TextField.Normal"})
    eg: display_interactive_components_for_user("notify",  {"title": "Done!", "message": "File saved.", "bg_color": "#27ae60", "duration_ms": "3000"}, mode="fire_and_forget")
    eg: display_interactive_components_for_user("progress",{"title": "Installing...", "message": "Please wait.", "progress": "-1"}, mode="fire_and_forget")
    """
    try:
        # ── Defaults for optional placeholders ───────────────────────────────
        defaults = {
            "confirm_label": "OK",
            "cancel_label": "Cancel",
            "placeholder": "",
            "echo_mode": "TextField.Normal",
            "bg_color": "#012946",
            "duration_ms": "3000",
            "progress": "-1",
        }
        merged = {**defaults, **placeholders}

        # ── Get and fill template ─────────────────────────────────────────────
        if template not in QML_TEMPLATES:
            return {
                "success": False,
                "error": f"Unknown template '{template}'. Available: {list(QML_TEMPLATES.keys())}"
            }

        qml = _fill_template(QML_TEMPLATES[template], merged)
        qml = _sanitize_qml(qml)
        qml_path = _write_qml(qml)

        # ── Launch Quickshell ─────────────────────────────────────────────────
        cmd = ["quickshell", "-p", qml_path]

        if mode == "fire_and_forget":
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env={**os.environ, "QT_QPA_PLATFORM": "wayland;xcb"}
            )
            return {
                "success": True,
                "mode": "fire_and_forget",
                "template": template,
                "pid": proc.pid,
                "qml_path": qml_path,
                "note": "Use kill_gui_window(pid) to close this window when done"
            }

        # Blocking mode — wait for exit code + stdout
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env={**os.environ, "QT_QPA_PLATFORM": "wayland;xcb"}
            )
            stdout, stderr = proc.communicate(timeout=timeout)
            exit_code = proc.returncode
            user_output = stdout.decode().strip()

        except subprocess.TimeoutExpired:
            proc.kill()
            os.unlink(qml_path)
            return {"success": False, "error": f"GUI timed out after {timeout}s — window closed"}

        os.unlink(qml_path)

        # ── Parse result by template ──────────────────────────────────────────
        if template == "confirm":
            return {
                "success": True,
                "template": "confirm",
                "confirmed": exit_code == 1,
                "exit_code": exit_code
            }

        elif template == "input":
            if exit_code == 0:
                return {"success": True, "template": "input", "cancelled": True, "user_input": None}
            return {
                "success": True,
                "template": "input",
                "cancelled": False,
                "user_input": user_output
            }

        elif template == "picker":
            if exit_code == 0:
                return {"success": True, "template": "picker", "cancelled": True, "selected_index": None, "selected_value": None}
            selected_index = exit_code - 1
            options_raw = merged.get("options", "[]")
            try:
                options = json.loads(options_raw)
                selected_value = options[selected_index] if 0 <= selected_index < len(options) else None
            except Exception:
                selected_value = None
            return {
                "success": True,
                "template": "picker",
                "cancelled": False,
                "selected_index": selected_index,
                "selected_value": selected_value
            }

        elif template in ("notify", "progress", "custom"):
            return {
                "success": True,
                "template": template,
                "exit_code": exit_code,
                "stdout": user_output,
                "stderr": stderr.decode().strip()
            }

        return {"success": True, "exit_code": exit_code, "stdout": user_output}

    except FileNotFoundError:
        return {"success": False, "error": "quickshell not found. Install from https://quickshell.outfoxxed.me"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@mcp.tool()
def initialize_project(ProjectName: str) -> Dict[str, Any]:
    """
    Initialize a new project with the given name
    eg: initialize_project("MyNewProject")
    The  project will be created in `/home/zerone/Documents/Projects`
    and will launch a Visual Studio Code instance in that directory.

    Next Step for the Agent:
    - Initialize a git repository in this path, then create a README.md
    """
    try:
        project_path = f"/home/zerone/Documents/Projects/{ProjectName}"
        subprocess.run(["mkdir", "-p", project_path], check=True)
        subprocess.run(["code", project_path], check=True)
        return {"status": "success", "message": f"Project '{ProjectName}' initialized at {project_path}"}
    except subprocess.CalledProcessError as e:
        return {"status": "error", "message": str(e)}

# SYSTEMCTL SERVICES
@mcp.tool()
def search_services(pattern: str) -> Dict[str, Any]:
    """
    Search for systemd services using a regex pattern.
    eg: search_services("nginx|apache") or search_services(".*sql.*")

    Returns a list of matching service names with their current state.
    Next Step for the Agent:
    - Use the returned service names with start/stop/enable/restart tools.
    """
    try:
        result = subprocess.run(
            ["systemctl", "list-units", "--type=service", "--all", "--no-pager", "--plain"],
            capture_output=True, text=True, check=True
        )
        services = []
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 4 and parts[0].endswith(".service"):
                name, load, active, sub = parts[0], parts[1], parts[2], parts[3]
                if re.search(pattern, name, re.IGNORECASE):
                    services.append({
                        "name": name,
                        "load": load,
                        "active": active,
                        "sub": sub,
                    })
        return {"status": "success", "matches": services, "count": len(services)}
    except subprocess.CalledProcessError as e:
        return {"status": "error", "message": e.stderr or str(e)}
    except re.error as e:
        return {"status": "error", "message": f"Invalid regex pattern: {e}"}


@mcp.tool()
def get_service_status(service_name: str) -> Dict[str, Any]:
    """
    Get the detailed status of a systemd service.
    eg: get_service_status("nginx.service") or get_service_status("nginx")

    Automatically appends `.service` if no suffix is provided.
    Next Step for the Agent:
    - Use start_service / stop_service / restart_service to change the state.
    """
    service_name = _normalize(service_name)
    try:
        result = subprocess.run(
            ["systemctl", "status", service_name, "--no-pager"],
            capture_output=True, text=True
        )
        # status returns exit code 3 when inactive — still useful output
        return {
            "status": "success",
            "service": service_name,
            "output": result.stdout or result.stderr,
            "active": result.returncode == 0,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
def start_service(service_name: str) -> Dict[str, Any]:
    """
    Start a systemd service.
    eg: start_service("nginx") or start_service("postgresql.service")

    Requires sufficient privileges (run the MCP server as root or with sudo access).
    Next Step for the Agent:
    - Verify with get_service_status that the service is now active.
    """
    return _run_systemctl("start", service_name)


@mcp.tool()
def stop_service(service_name: str) -> Dict[str, Any]:
    """
    Stop a systemd service.
    eg: stop_service("nginx") or stop_service("postgresql.service")

    Requires sufficient privileges (run the MCP server as root or with sudo access).
    Next Step for the Agent:
    - Verify with get_service_status that the service is now inactive.
    """
    return _run_systemctl("stop", service_name)


@mcp.tool()
def restart_service(service_name: str) -> Dict[str, Any]:
    """
    Restart a systemd service.
    eg: restart_service("nginx") or restart_service("postgresql.service")

    Requires sufficient privileges (run the MCP server as root or with sudo access).
    Next Step for the Agent:
    - Verify with get_service_status that the service came back up cleanly.
    """
    return _run_systemctl("restart", service_name)


@mcp.tool()
def enable_service(service_name: str) -> Dict[str, Any]:
    """
    Enable a systemd service to start automatically at boot.
    eg: enable_service("nginx") or enable_service("postgresql.service")

    This does NOT start the service immediately — combine with start_service if needed.
    Requires sufficient privileges (run the MCP server as root or with sudo access).
    Next Step for the Agent:
    - Optionally call start_service if the service should also be running right now.
    """
    return _run_systemctl("enable", service_name)


@mcp.tool()
def disable_service(service_name: str) -> Dict[str, Any]:
    """
    Disable a systemd service so it no longer starts at boot.
    eg: disable_service("nginx") or disable_service("postgresql.service")

    This does NOT stop the service immediately — combine with stop_service if needed.
    Requires sufficient privileges (run the MCP server as root or with sudo access).
    Next Step for the Agent:
    - Optionally call stop_service if the service should also be stopped right now.
    """
    return _run_systemctl("disable", service_name)


# ── helpers ──────────────────────────────────────────────────────────────────

def _normalize(name: str) -> str:
    """Append .service suffix if the caller omitted it."""
    return name if "." in name else f"{name}.service"


def _run_systemctl(action: str, service_name: str) -> Dict[str, Any]:
    """Shared runner for all mutating systemctl commands."""
    service_name = _normalize(service_name)
    try:
        result = subprocess.run(
            ["systemctl", action, service_name],
            capture_output=True, text=True, check=True
        )
        return {
            "status": "success",
            "service": service_name,
            "action": action,
            "output": result.stdout or f"Service '{service_name}' {action}ed successfully.",
        }
    except subprocess.CalledProcessError as e:
        return {
            "status": "error",
            "service": service_name,
            "action": action,
            "message": e.stderr or str(e),
        }

# RIGEL Claude Code Integration
_agents: Dict[str, Dict] = {}

def _strip_ansi(text: str) -> str:
    ansi_escape = re.compile(r'\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~]|\][^\x07]*\x07)')
    return ansi_escape.sub('', text)

def _clean_output(text: str) -> str:
    text = _strip_ansi(text)
    text = text.replace('\r\r\n', '\n').replace('\r\n', '\n').replace('\r', '\n')
    lines = [l for l in text.splitlines() if l.strip()]
    return '\n'.join(lines)

def _read_output(child, timeout=2) -> str:
    chunks = []
    while True:
        try:
            chunk = child.read_nonblocking(size=10000, timeout=timeout)
            chunks.append(chunk)
        except (pexpect.TIMEOUT, pexpect.EOF):
            break
    return ''.join(chunks)

def _append_log(agent_id: str, role: str, message: str):
    agent = _agents.get(agent_id)
    if not agent:
        return
    entry = {
        "timestamp": datetime.now().isoformat(),
        "role": role,
        "message": message
    }
    agent["log"].append(entry)
    if agent.get("log_file"):
        with open(agent["log_file"], 'a') as f:
            f.write(json.dumps(entry) + '\n')


@mcp.tool()
def launch_agent(
    agent_id: str,
    model: str = "qwen3.5:cloud",
    working_dir: Optional[str] = None,
    log_file: Optional[str] = None
) -> Dict[str, Any]:
    """
    Launch a Claude Code agent in the background.
    Returns agent_id and status. Use agent_id for all further interactions.
    eg: launch_agent("my_agent", model="qwen3.5:cloud", working_dir="/home/user/project")
    """
    if agent_id in _agents:
        return {"success": False, "error": f"Agent '{agent_id}' already exists. Kill it first or use a different ID."}

    try:
        env = os.environ.copy()
        if working_dir:
            os.makedirs(working_dir, exist_ok=True)

        child = pexpect.spawn(
            f'ollama launch claude --model {model}',
            encoding='utf-8',
            timeout=60,
            cwd=working_dir or os.getcwd(),
            env=env
        )

        # Respond to terminal capability queries
        time.sleep(2)
        child.send('\x1b]11;rgb:0000/0000/0000\x1b\\')
        child.send('\x1b[1;1R')
        time.sleep(3)

        # Read and confirm trust prompt
        _read_output(child)
        child.send('\r')
        time.sleep(4)

        # Read startup screen
        startup = _clean_output(_read_output(child))

        _agents[agent_id] = {
            "agent_id": agent_id,
            "model": model,
            "child": child,
            "status": "ready",
            "working_dir": working_dir or os.getcwd(),
            "log_file": log_file,
            "log": [],
            "last_output": startup,
            "launched_at": datetime.now().isoformat(),
            "last_active": datetime.now().isoformat(),
        }

        _append_log(agent_id, "system", f"Agent launched. Startup: {startup}")

        return {
            "success": True,
            "agent_id": agent_id,
            "status": "ready",
            "model": model,
            "working_dir": working_dir or os.getcwd(),
            "startup_output": startup
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def send_prompt(agent_id: str, prompt: str, wait_seconds: int = 5) -> Dict[str, Any]:
    """
    Send a prompt to a running Claude Code agent and return its response.
    eg: send_prompt("my_agent", "Create a hello world Python script")
    """
    agent = _agents.get(agent_id)
    if not agent:
        return {"success": False, "error": f"No agent with ID '{agent_id}'. Launch one first."}

    if agent["status"] == "busy":
        return {"success": False, "error": f"Agent '{agent_id}' is busy. Wait or check state."}

    try:
        child = agent["child"]
        agent["status"] = "busy"
        agent["last_active"] = datetime.now().isoformat()

        _append_log(agent_id, "user", prompt)
        child.send(prompt + '\r')
        time.sleep(wait_seconds)

        output = _clean_output(_read_output(child))
        agent["last_output"] = output
        agent["status"] = "ready"
        agent["last_active"] = datetime.now().isoformat()

        _append_log(agent_id, "agent", output)

        return {
            "success": True,
            "agent_id": agent_id,
            "output": output
        }

    except Exception as e:
        agent["status"] = "error"
        return {"success": False, "error": str(e)}


@mcp.tool()
def get_agent_output(agent_id: str) -> Dict[str, Any]:
    """
    Read the latest output from a Claude Code agent without sending anything.
    Useful for polling a busy agent.
    eg: get_agent_output("my_agent")
    """
    agent = _agents.get(agent_id)
    if not agent:
        return {"success": False, "error": f"No agent with ID '{agent_id}'."}

    try:
        child = agent["child"]
        output = _clean_output(_read_output(child, timeout=1))

        if output:
            agent["last_output"] = output
            agent["last_active"] = datetime.now().isoformat()
            _append_log(agent_id, "agent", output)

        return {
            "success": True,
            "agent_id": agent_id,
            "status": agent["status"],
            "output": output or agent["last_output"],
            "last_active": agent["last_active"]
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def get_agent_state(agent_id: str) -> Dict[str, Any]:
    """
    Check the state of a Claude Code agent — status, uptime, last activity.
    eg: get_agent_state("my_agent")
    """
    agent = _agents.get(agent_id)
    if not agent:
        return {"success": False, "error": f"No agent with ID '{agent_id}'."}

    child = agent["child"]
    alive = child.isalive()

    if not alive and agent["status"] != "dead":
        agent["status"] = "dead"

    return {
        "success": True,
        "agent_id": agent_id,
        "status": agent["status"],
        "alive": alive,
        "model": agent["model"],
        "working_dir": agent["working_dir"],
        "launched_at": agent["launched_at"],
        "last_active": agent["last_active"],
        "log_entries": len(agent["log"]),
        "last_output_preview": agent["last_output"][:300] if agent["last_output"] else ""
    }


@mcp.tool()
def list_agents() -> Dict[str, Any]:
    """
    List all running and dead Claude Code agents.
    eg: list_agents()
    """
    result = []
    for agent_id, agent in _agents.items():
        alive = agent["child"].isalive()
        if not alive and agent["status"] != "dead":
            agent["status"] = "dead"
        result.append({
            "agent_id": agent_id,
            "status": agent["status"],
            "alive": alive,
            "model": agent["model"],
            "working_dir": agent["working_dir"],
            "launched_at": agent["launched_at"],
            "last_active": agent["last_active"],
        })

    return {"success": True, "agents": result, "total": len(result)}


@mcp.tool()
def get_agent_log(agent_id: str, last_n: int = 20) -> Dict[str, Any]:
    """
    Get the conversation log of a Claude Code agent.
    eg: get_agent_log("my_agent", last_n=10)
    """
    agent = _agents.get(agent_id)
    if not agent:
        return {"success": False, "error": f"No agent with ID '{agent_id}'."}

    log = agent["log"][-last_n:] if last_n else agent["log"]
    return {
        "success": True,
        "agent_id": agent_id,
        "total_entries": len(agent["log"]),
        "returned": len(log),
        "log": log
    }


@mcp.tool()
def kill_agent(agent_id: str) -> Dict[str, Any]:
    """
    Kill a Claude Code agent and remove it from the registry.
    eg: kill_agent("my_agent")
    """
    agent = _agents.get(agent_id)
    if not agent:
        return {"success": False, "error": f"No agent with ID '{agent_id}'."}

    try:
        child = agent["child"]
        if child.isalive():
            child.send('\x03')  # Ctrl+C
            time.sleep(0.5)
            child.close(force=True)

        _append_log(agent_id, "system", "Agent killed.")
        agent["status"] = "dead"
        del _agents[agent_id]

        return {"success": True, "agent_id": agent_id, "message": "Agent killed and removed."}

    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def restart_agent(agent_id: str) -> Dict[str, Any]:
    """
    Kill and relaunch a Claude Code agent with the same config.
    eg: restart_agent("my_agent")
    """
    agent = _agents.get(agent_id)
    if not agent:
        return {"success": False, "error": f"No agent with ID '{agent_id}'."}

    model = agent["model"]
    working_dir = agent["working_dir"]
    log_file = agent["log_file"]

    kill_result = kill_agent(agent_id)
    if not kill_result["success"]:
        return {"success": False, "error": f"Failed to kill agent: {kill_result['error']}"}

    return launch_agent(agent_id, model=model, working_dir=working_dir, log_file=log_file)


# ── Companion tool: kill a fire-and-forget window ────────────────────────────

@mcp.tool()
def kill_gui_window(pid: int) -> Dict[str, Any]:
    """
    Kill a fire-and-forget Quickshell GUI window by its PID.
    Use this to close progress windows or runtime apps launched with quickshell_gui.
    eg: kill_gui_window(12345)
    """
    try:
        import signal
        os.kill(pid, signal.SIGTERM)
        return {"success": True, "killed_pid": pid}
    except ProcessLookupError:
        return {"success": False, "error": f"No process with PID {pid} found"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def initialize_auxiliary_compute_unit() -> Dict[str, Any]:
    """
    Initialize the ztOS Auxiliary Compute Unit. 
    """
    try:
        # os.system(adb kill-server && scrcpy  --turn-screen-off --max-size 1024&)
        subprocess.run(["adb", "kill-server"], check=True)
        subprocess.Popen(["scrcpy", "--turn-screen-off", "--max-size", "1024"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return {"success": True, "message": "Auxiliary Compute Unit initialized successfully"}
    except Exception as e:
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    # Register all tools for REST API
    TOOL_REGISTRY.update({
        # Original tools
        "current_time": current_time,
        "show_available_commands": show_available_commands,
        # "create_file": create_file,
        # "create_folder": create_folder,
        # LEGACY TOOLS ############
        # "find_executable": find_executable,
        # "start_application": start_application,
        # "get_pids": get_pids,
        # "kill_application": kill_application,
        # "kill_pid": kill_pid,
        ###########################
        "Initialize Zerone Laboratories Auxiliary Compute Interface": initialize_auxiliary_compute_unit,
        "send_dbus_notification": send_dbus_notification,
        "list_usb_devices": check_usb_devices,
        "network_status": check_network_status,
        "system_specs": get_system_specs,
        # KDE Plasma tools
        "set_volume": set_volume,
        "get_volume": get_volume,
        "set_brightness": set_brightness,
        "toggle_night_color": toggle_night_color,
        "toggle_do_not_disturb": toggle_do_not_disturb,
        "toggle_wifi": toggle_wifi,
        "toggle_bluetooth": toggle_bluetooth,
        "list_running_apps": list_running_apps,
        "open_app": open_app,
        "close_app_by_name": close_app_by_name,
        "close_window_by_title": close_window_by_title,
        "focus_window": focus_window,
        "switch_virtual_desktop": switch_virtual_desktop,
        "get_clipboard_content": get_clipboard_content,
        "set_clipboard_content": set_clipboard_content,
        "set_wallpaper": set_wallpaper,
        "lock_screen": lock_screen,
        "take_screenshot": take_screenshot,
        "run_krunner": run_krunner,
        "media_control": media_control,
        "get_media_playback_info": get_media_info,
        "get_battery_status": get_battery_status,
        "set_screen_timeout": set_screen_timeout,
        "get_wifi_networks": get_wifi_networks,
        "connect_wifi": connect_wifi,
        "open_system_settings": open_system_settings,
        "get_display_info": get_display_info,
        "set_display_resolution": set_display_resolution,
        "run_bash_command": run_bash_command,
        "ztos_aci_list_devices": ztos_aci_list_devices,
        "ztos_aci_send_sms": ztos_aci_send_sms,
        "ztos_aci_send_notification": ztos_aci_send_notification,
        "ztos_aci_ring_device": ztos_aci_ring_device,
        "ztos_aci_send_file": ztos_aci_send_file,
        "ztos_aci_share_url": ztos_aci_share_url,
        "ztos_aci_get_device_info": ztos_aci_get_device_info,
        "ztos_aci_run_command": ztos_aci_run_command,
        "ztos_aci_set_volume": ztos_aci_set_volume,
        "ztos_aci_list_user_contacts": ztos_aci_list_user_contacts,
        #WEB INTERACTIONS
        "search_web": search_web,
        #GUI INTERACTIONS
        "display_interactive_components_for_user": display_interactive_components_for_user,
        "initialize_a_project": initialize_project,
        # SYSTEMCTL INTERACTIONS
        "search_services": search_services,
        "get_service_status": get_service_status,
        "start_service": start_service,
        "stop_service": stop_service,
        "restart_service": restart_service,
        "enable_service": enable_service,
        "disable_service": disable_service,
        # CLAUDE CODE AGENT INTERACTIONS
        # "launch_agent": launch_agent,
        # "send_prompt": send_prompt,
        # "get_agent_output": get_agent_output,
        # "get_agent_state": get_agent_state,
        # "list_agents": list_agents,
        # "get_agent_log": get_agent_log,
        # "kill_agent": kill_agent,
        # "restart_agent": restart_agent,
    })
    #"browser_interactions": browser_agent_task,  [DOESNT WORK WITHOUT A OPENAI KEY]

    # Start REST API in background thread
    rest_thread = threading.Thread(target=start_rest_api, args=(8002,), daemon=True)
    rest_thread.start()

    # Run MCP server
    mcp.run(transport="sse")
