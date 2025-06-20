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

from typing import List
from mcp.server.fastmcp import FastMCP
import subprocess
import os
import json
from datetime import datetime

mcp = FastMCP("Rigel Tool", port=8001)


@mcp.tool()
def current_time() -> str:
    """Returns the current time."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

@mcp.tool()
def run_system_command(command: str) -> str:
    """Run any command on the Linux shell and return the output.
    
    Args:
        command: The shell command to execute
        
    Returns:
        The output of the command or error message
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            return f"Command succeeded:\n{result.stdout}"
        else:
            return f"Command failed (exit code {result.returncode}):\n{result.stderr}"
            
    except subprocess.TimeoutExpired:
        return "Command timed out after 30 seconds"
    except Exception as e:
        return f"Error executing command: {str(e)}"

@mcp.tool()
def read_file(file_path: str) -> str:
    """Read the contents of a file.
    
    Args:
        file_path: Path to the file to read
        
    Returns:
        The contents of the file or error message
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    except Exception as e:
        return f"Error reading file: {str(e)}"

@mcp.tool()
def write_file(file_path: str, content: str) -> str:
    """Write content to a file.
    
    Args:
        file_path: Path to the file to write
        content: Content to write to the file
        
    Returns:
        Success message or error message
    """
    try:
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(content)
        return f"Successfully wrote to {file_path}"
    except Exception as e:
        return f"Error writing file: {str(e)}"

@mcp.tool()
def list_directory(directory_path: str = ".") -> str:
    """List the contents of a directory.
    
    Args:
        directory_path: Path to the directory to list (defaults to current directory)
        
    Returns:
        List of files and directories or error message
    """
    try:
        items = os.listdir(directory_path)
        result = []
        for item in sorted(items):
            full_path = os.path.join(directory_path, item)
            if os.path.isdir(full_path):
                result.append(f"📁 {item}/")
            else:
                result.append(f"📄 {item}")
        return "\n".join(result)
    except Exception as e:
        return f"Error listing directory: {str(e)}"

@mcp.tool()
def get_system_info() -> str:
    """Get basic system information.
    
    Returns:
        System information as a JSON string
    """
    try:
        info = {
            "current_directory": os.getcwd(),
            "user": os.getenv("USER", "unknown"),
            "home": os.getenv("HOME", "unknown"),
            "shell": os.getenv("SHELL", "unknown"),
            "python_version": subprocess.run(["python3", "--version"], capture_output=True, text=True).stdout.strip()
        }
        return json.dumps(info, indent=2)
    except Exception as e:
        return f"Error getting system info: {str(e)}"

if __name__ == "__main__":
    mcp.run(transport="sse")
