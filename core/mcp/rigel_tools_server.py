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


@mcp.tool()
def current_time() -> Dict[str, Any]:
    """Returns the current time."""
    return {"time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

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

    return {
        "count": len(commands),
        "commands": sorted(set(commands))
    }

@mcp.tool()
def create_folder(directory) -> Dict[str, Any]:
    try:
        subprocess.run(["touch", f"{directory}"])
        return {"output": f"File created at {directory}"}
    except:
        return {"output": "Failed to create file"}

if __name__ == "__main__":
    mcp.run(transport="sse")
