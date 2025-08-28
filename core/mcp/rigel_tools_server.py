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
def run_system_command(command: str) -> Dict[str, Any]:
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
            return {"result": "success", "output": result.stdout}
        else:
            return {"result": "error", "code": result.returncode, "error": result.stderr}
            
    except subprocess.TimeoutExpired:
        return {"result": "error", "error": "Command timed out after 30 seconds"}
    except Exception as e:
        return {"result": "error", "error": f"Error executing command: {str(e)}"}

@mcp.tool()
def read_file(file_path: str) -> Dict[str, Any]:
    """Read the contents of a file.
    
    Args:
        file_path: Path to the file to read
        
    Returns:
        The contents of the file or error message
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
            return {"result": "success", "content": content}
    except Exception as e:
        return {"result": "error", "error": f"Error reading file: {str(e)}"}

@mcp.tool()
def write_file(file_path: str, content: str) -> Dict[str, Any]:
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
        return {"result": "success", "message": f"Successfully wrote to {file_path}"}
    except Exception as e:
        return {"result": "error", "error": f"Error writing file: {str(e)}"}

@mcp.tool()
def list_directory(directory_path: str = ".") -> Dict[str, Any]:
    """List the contents of a directory.
    
    Args:
        directory_path: Path to the directory to list (defaults to current directory)
        
    Returns:
        List of files and directories or error message
    """
    try:
        items = os.listdir(directory_path)
        files = []
        directories = []
        
        for item in sorted(items):
            full_path = os.path.join(directory_path, item)
            if os.path.isdir(full_path):
                directories.append(item)
            else:
                files.append(item)
                
        return {
            "result": "success",
            "path": directory_path,
            "directories": directories,
            "files": files
        }
    except Exception as e:
        return {"result": "error", "error": f"Error listing directory: {str(e)}"}

@mcp.tool()
def get_system_info() -> Dict[str, Any]:
    """Get basic system information.
    
    Returns:
        System information as a dictionary
    """
    try:
        # Use OSTools if available for more detailed info
        if OS_TOOLS_AVAILABLE:
            result = os_tools.get_detailed_system_info()
            if result["success"]:
                return {"result": "success", "info": result["info"]}
        
        # Fallback to basic info
        info = {
            "current_directory": os.getcwd(),
            "user": os.getenv("USER", "unknown"),
            "home": os.getenv("HOME", "unknown"),
            "shell": os.getenv("SHELL", "unknown"),
            "python_version": subprocess.run(["python3", "--version"], capture_output=True, text=True).stdout.strip()
        }
        return {"result": "success", "info": info}
    except Exception as e:
        return {"result": "error", "error": f"Error getting system info: {str(e)}"}

@mcp.tool()
def create_temp_program(content: str, file_extension: str = ".py") -> Dict[str, Any]:
    """Create a temporary program file with the given content.
    
    Args:
        content: Source code to write to the file
        file_extension: File extension for the temporary file (defaults to .py)
        
    Returns:
        Information about the created file or error details
    """
    if not OS_TOOLS_AVAILABLE:
        return {"result": "error", "error": "OSTools module not available"}
    
    try:
        result = os_tools.create_temp_program(content, file_extension)
        if result["success"]:
            return {
                "result": "success", 
                "file_path": result["file_path"],
                "file_name": result["file_name"]
            }
        else:
            return {"result": "error", "error": result.get("error", "Unknown error")}
    except Exception as e:
        return {"result": "error", "error": f"Error creating temporary program: {str(e)}"}

@mcp.tool()
def execute_temp_program(file_path: str, args: List[str] = None, 
                        interpreter: str = None, timeout: int = None) -> Dict[str, Any]:
    """Execute a temporary program with optional arguments and interpreter.
    
    Args:
        file_path: Path to the temporary program file
        args: List of command-line arguments to pass to the program
        interpreter: Interpreter to use (e.g., "python", "node", "bash")
                    If None, determined by file extension
        timeout: Execution timeout in seconds (defaults to 30)
        
    Returns:
        Execution result with stdout/stderr
    """
    if not OS_TOOLS_AVAILABLE:
        return {"result": "error", "error": "OSTools module not available"}
    
    try:
        result = os_tools.execute_temp_program(
            file_path=file_path,
            args=args if args else [],
            interpreter=interpreter,
            timeout=timeout
        )
        
        if result["success"]:
            return {
                "result": "success",
                "stdout": result["stdout"],
                "stderr": result["stderr"],
                "exit_code": result["exit_code"]
            }
        else:
            return {"result": "error", "error": result.get("error", "Unknown error")}
    except Exception as e:
        return {"result": "error", "error": f"Error executing temporary program: {str(e)}"}

@mcp.tool()
def create_and_execute_program(content: str, file_extension: str = ".py", 
                              args: List[str] = None, interpreter: str = None, 
                              timeout: int = None) -> Dict[str, Any]:
    """Create and execute a temporary program in one operation.
    
    Args:
        content: Source code content
        file_extension: File extension
        args: Program arguments
        interpreter: Program interpreter
        timeout: Execution timeout in seconds
        
    Returns:
        Execution result with stdout/stderr
    """
    if not OS_TOOLS_AVAILABLE:
        return {"result": "error", "error": "OSTools module not available"}
    
    try:
        result = os_tools.create_and_execute_program(
            content=content,
            file_extension=file_extension,
            args=args if args else [],
            interpreter=interpreter,
            timeout=timeout,
            cleanup=True
        )
        
        if result["success"]:
            return {
                "result": "success",
                "stdout": result["stdout"],
                "stderr": result["stderr"],
                "exit_code": result["exit_code"],
                "file_info": result.get("file_info", {})
            }
        else:
            return {"result": "error", "error": result.get("error", "Unknown error")}
    except Exception as e:
        return {"result": "error", "error": f"Error in create_and_execute_program: {str(e)}"}

@mcp.tool()
def get_os_environment() -> Dict[str, Any]:
    """Get detailed information about the operating system environment.
    
    Returns:
        Comprehensive OS environment details
    """
    try:
        env_vars = dict(os.environ)
        
        # Remove sensitive information
        for key in ['PASSWORD', 'PASSWD', 'SECRET', 'KEY', 'TOKEN', 'AUTH']:
            for env_key in list(env_vars.keys()):
                if key in env_key.upper():
                    env_vars[env_key] = "[REDACTED]"
        
        info = {
            "platform": {
                "system": platform.system(),
                "release": platform.release(),
                "version": platform.version(),
                "architecture": platform.machine(),
                "processor": platform.processor(),
                "node": platform.node()
            },
            "python": {
                "version": platform.python_version(),
                "path": sys.executable,
                "implementation": platform.python_implementation()
            },
            "environment": {
                "user": os.getenv("USER", "unknown"),
                "home": os.getenv("HOME", "unknown"),
                "shell": os.getenv("SHELL", "unknown"),
                "path": os.getenv("PATH", "unknown"),
                "lang": os.getenv("LANG", "unknown")
            }
        }
        
        return {"result": "success", "info": info, "env_vars": env_vars}
    except Exception as e:
        return {"result": "error", "error": f"Error getting OS environment: {str(e)}"}

@mcp.tool()
def manage_files(operation: str, source: str, destination: str = None, content: str = None) -> Dict[str, Any]:
    """Perform file operations such as copy, move, delete, create.
    
    Args:
        operation: The operation to perform ('copy', 'move', 'delete', 'create')
        source: Source file or directory path
        destination: Destination path (required for copy/move)
        content: File content (for create operation)
        
    Returns:
        Operation result or error
    """
    try:
        operation = operation.lower()
        
        if operation == "copy":
            if not destination:
                return {"result": "error", "error": "Destination path required for copy operation"}
            
            if os.path.isdir(source):
                if os.path.exists(destination):
                    return {"result": "error", "error": f"Destination directory already exists: {destination}"}
                shutil.copytree(source, destination)
                return {"result": "success", "message": f"Directory copied from {source} to {destination}"}
            else:
                shutil.copy2(source, destination)
                return {"result": "success", "message": f"File copied from {source} to {destination}"}
                
        elif operation == "move":
            if not destination:
                return {"result": "error", "error": "Destination path required for move operation"}
                
            shutil.move(source, destination)
            return {"result": "success", "message": f"Moved {source} to {destination}"}
            
        elif operation == "delete":
            if os.path.isdir(source):
                shutil.rmtree(source)
                return {"result": "success", "message": f"Directory deleted: {source}"}
            else:
                os.remove(source)
                return {"result": "success", "message": f"File deleted: {source}"}
                
        elif operation == "create":
            if not content:
                return {"result": "error", "error": "Content required for create operation"}
                
            os.makedirs(os.path.dirname(os.path.abspath(source)), exist_ok=True)
            with open(source, 'w', encoding='utf-8') as f:
                f.write(content)
            return {"result": "success", "message": f"File created: {source}"}
            
        else:
            return {"result": "error", "error": f"Unsupported operation: {operation}"}
    except Exception as e:
        return {"result": "error", "error": f"Error in manage_files: {str(e)}"}

if __name__ == "__main__":
    mcp.run(transport="sse")
