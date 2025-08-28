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

"""
OS Tools module for RIGEL Engine.
Provides advanced OS operations capabilities including command execution,
temporary program creation and execution, and system operations.
"""

import os
import subprocess
import tempfile
import shutil
import uuid
import time
import platform
import json
import sys
from typing import Dict, Any, List, Optional, Union, Tuple
from core.logger import SysLog

# Initialize logger
syslog = SysLog(name="OSTools", level="DEBUG", log_file="rigel.log")

class OSTools:
    """
    Provides OS-level operations for the RIGEL Engine.
    
    This class extends RIGEL's capabilities with advanced OS interactions:
    - Safe command execution with timeout and output capturing
    - Temporary program creation and execution
    - File and directory operations
    - System information gathering
    """
    
    def __init__(self, temp_dir: str = None, max_execution_time: int = 30):
        """
        Initialize OSTools with configuration parameters.
        
        Args:
            temp_dir: Directory to use for temporary files. If None, system temp dir is used.
            max_execution_time: Maximum execution time for commands in seconds (default: 30)
        """
        self.max_execution_time = max_execution_time
        
        if temp_dir:
            self.temp_dir = temp_dir
            os.makedirs(self.temp_dir, exist_ok=True)
        else:
            self.temp_dir = tempfile.gettempdir()
            
        self.temp_files = []  # Track temporary files for cleanup
        syslog.info(f"OSTools initialized with temp_dir: {self.temp_dir}")
    
    def execute_command(self, command: str, timeout: int = None, 
                        working_dir: str = None, env: Dict[str, str] = None) -> Dict[str, Any]:
        """
        Execute a system command safely with timeout and output capture.
        
        Args:
            command: The shell command to execute
            timeout: Command timeout in seconds (defaults to self.max_execution_time)
            working_dir: Directory to execute command in (defaults to current directory)
            env: Environment variables to set for command execution
            
        Returns:
            Dictionary with command result and output
        """
        if timeout is None:
            timeout = self.max_execution_time
            
        try:
            syslog.info(f"Executing command: {command}")
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=working_dir,
                env=env
            )
            
            response = {
                "success": result.returncode == 0,
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "command": command
            }
            
            if result.returncode != 0:
                syslog.warning(f"Command failed with exit code {result.returncode}: {command}")
                syslog.warning(f"Error: {result.stderr}")
            
            return response
        except subprocess.TimeoutExpired:
            syslog.error(f"Command timed out after {timeout} seconds: {command}")
            return {
                "success": False,
                "error": f"Command timed out after {timeout} seconds",
                "command": command
            }
        except Exception as e:
            syslog.error(f"Error executing command '{command}': {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "command": command
            }
    
    def create_temp_program(self, content: str, file_extension: str = ".py") -> Dict[str, Any]:
        """
        Create a temporary program file with the given content.
        
        Args:
            content: Source code to write to the file
            file_extension: File extension for the temporary file (defaults to .py)
            
        Returns:
            Dictionary with file information
        """
        try:
            # Generate a unique identifier for the file
            file_id = str(uuid.uuid4())[:8]
            filename = f"rigel_temp_{file_id}{file_extension}"
            file_path = os.path.join(self.temp_dir, filename)
            
            # Write content to the file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
                
            # Make the file executable on Unix-like systems
            if platform.system() != "Windows":
                os.chmod(file_path, 0o755)
                
            # Add to tracking list for cleanup
            self.temp_files.append(file_path)
            
            syslog.info(f"Created temporary program file: {file_path}")
            return {
                "success": True,
                "file_path": file_path,
                "file_name": filename
            }
        except Exception as e:
            syslog.error(f"Error creating temporary program: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def execute_temp_program(self, file_path: str, args: List[str] = None, 
                            interpreter: str = None, timeout: int = None) -> Dict[str, Any]:
        """
        Execute a temporary program with optional arguments and interpreter.
        
        Args:
            file_path: Path to the temporary program file
            args: List of command-line arguments to pass to the program
            interpreter: Interpreter to use (e.g., "python", "node", "bash")
                        If None, determined by file extension
            timeout: Execution timeout in seconds
            
        Returns:
            Dictionary with execution result
        """
        if not os.path.exists(file_path):
            syslog.error(f"Temporary program file not found: {file_path}")
            return {
                "success": False,
                "error": f"File not found: {file_path}"
            }
            
        if args is None:
            args = []
            
        # Determine interpreter based on file extension if not specified
        if interpreter is None:
            ext = os.path.splitext(file_path)[1].lower()
            if ext == '.py':
                interpreter = sys.executable
            elif ext == '.js':
                interpreter = 'node'
            elif ext in ['.sh', '.bash']:
                interpreter = 'bash'
            elif ext in ['.pl', '.perl']:
                interpreter = 'perl'
            elif ext in ['.rb', '.ruby']:
                interpreter = 'ruby'
            elif ext in ['.php']:
                interpreter = 'php'
            elif ext in ['.r']:
                interpreter = 'Rscript'
            
        # Build command
        if interpreter:
            cmd_parts = [interpreter, file_path] + args
            command = ' '.join(cmd_parts)
        else:
            # For executable files (on Unix-like systems)
            command = f"{file_path} {' '.join(args)}"
            
        syslog.info(f"Executing temporary program: {command}")
        result = self.execute_command(command, timeout=timeout)
        
        return result
    
    def create_and_execute_program(self, content: str, file_extension: str = ".py", 
                                  args: List[str] = None, interpreter: str = None, 
                                  timeout: int = None, cleanup: bool = True) -> Dict[str, Any]:
        """
        Create and execute a temporary program in one operation.
        
        Args:
            content: Source code content
            file_extension: File extension
            args: Program arguments
            interpreter: Program interpreter
            timeout: Execution timeout
            cleanup: Whether to delete the temporary file after execution
            
        Returns:
            Dictionary with execution result
        """
        # Create the temporary program
        create_result = self.create_temp_program(content, file_extension)
        if not create_result["success"]:
            return create_result
            
        file_path = create_result["file_path"]
        
        try:
            # Execute the program
            result = self.execute_temp_program(
                file_path=file_path,
                args=args,
                interpreter=interpreter,
                timeout=timeout
            )
            
            # Add file info to result
            result["file_info"] = create_result
            
            # Clean up if requested
            if cleanup:
                try:
                    os.remove(file_path)
                    self.temp_files.remove(file_path)
                    result["cleanup"] = "success"
                except Exception as e:
                    result["cleanup"] = f"failed: {str(e)}"
                    
            return result
        except Exception as e:
            syslog.error(f"Error in create_and_execute_program: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "file_info": create_result
            }
    
    def get_detailed_system_info(self) -> Dict[str, Any]:
        """
        Get detailed system information.
        
        Returns:
            Dictionary with extensive system information
        """
        try:
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
                    "implementation": platform.python_implementation(),
                    "compiler": platform.python_compiler(),
                    "build": platform.python_build()
                },
                "environment": {
                    "user": os.getenv("USER", "unknown"),
                    "home": os.getenv("HOME", "unknown"),
                    "shell": os.getenv("SHELL", "unknown"),
                    "path": os.getenv("PATH", "unknown"),
                    "lang": os.getenv("LANG", "unknown"),
                    "term": os.getenv("TERM", "unknown"),
                    "display": os.getenv("DISPLAY", "unknown")
                },
                "current": {
                    "working_directory": os.getcwd(),
                    "process_id": os.getpid(),
                    "parent_process_id": os.getppid()
                }
            }
            
            # Add uptime on Unix-like systems
            if platform.system() != "Windows":
                try:
                    with open('/proc/uptime', 'r') as f:
                        uptime_seconds = float(f.readline().split()[0])
                        uptime_str = self._format_uptime(uptime_seconds)
                        info["system"] = {"uptime_seconds": uptime_seconds, "uptime": uptime_str}
                except:
                    pass
                    
            return {
                "success": True,
                "info": info
            }
        except Exception as e:
            syslog.error(f"Error getting detailed system info: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _format_uptime(self, seconds: float) -> str:
        """Format uptime seconds into a human-readable string."""
        days, remainder = divmod(seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        parts = []
        if days:
            parts.append(f"{int(days)} {'day' if int(days) == 1 else 'days'}")
        if hours:
            parts.append(f"{int(hours)} {'hour' if int(hours) == 1 else 'hours'}")
        if minutes:
            parts.append(f"{int(minutes)} {'minute' if int(minutes) == 1 else 'minutes'}")
        if seconds or not parts:
            parts.append(f"{int(seconds)} {'second' if int(seconds) == 1 else 'seconds'}")
            
        return ", ".join(parts)
    
    def cleanup(self) -> Dict[str, Any]:
        """
        Clean up all temporary files created by this instance.
        
        Returns:
            Dictionary with cleanup results
        """
        results = {"success": True, "deleted": [], "failed": []}
        
        for file_path in self.temp_files[:]:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    results["deleted"].append(file_path)
                self.temp_files.remove(file_path)
            except Exception as e:
                syslog.warning(f"Failed to delete temporary file {file_path}: {str(e)}")
                results["failed"].append({"path": file_path, "error": str(e)})
                results["success"] = False
                
        return results
    
    def __del__(self):
        """Cleanup temporary files upon object destruction."""
        self.cleanup()

# Example usage
if __name__ == "__main__":
    os_tools = OSTools()
    
    # Example: Run a simple command
    result = os_tools.execute_command("ls -la")
    print(f"Command execution result: {result['success']}")
    print(f"Output: {result['stdout']}")
    
    # Example: Create and execute a Python program
    python_code = """
import sys
import os
import platform

print(f"Hello from a temporary Python program!")
print(f"Python version: {platform.python_version()}")
print(f"Arguments: {sys.argv[1:]}")
print(f"Current directory: {os.getcwd()}")
"""

    program_result = os_tools.create_and_execute_program(
        content=python_code,
        args=["arg1", "arg2"],
        cleanup=True
    )
    
    print(f"Program execution result: {program_result['success']}")
    print(f"Output: {program_result['stdout']}")
    
    # Example: Get detailed system information
    sys_info = os_tools.get_detailed_system_info()
    print(f"System info: {json.dumps(sys_info['info'], indent=2)}")
